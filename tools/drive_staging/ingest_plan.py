#!/usr/bin/env python3
"""ingest_plan.py -- turn a staged historical drive's .czi + project claims into a per-file ingest plan,
a hard-link farm and one generated ingest config per batch.

PROFILES (`--profile`, default drives_2026-09). Everything drive-specific -- inputs, output folders,
drive labels, the config folder, the batch cap, the one project an ingest may create, the hand-recorded
re-save decisions -- lives in PROFILES below; `use_profile()` rebinds the module constants, so the
helpers and the sibling tools (ingest_check.py, ingest_verify.py, run_drives_batch.sh) work on any of
them:

  drives_2026-09   the two operator drives FRIO-X6 + MFB-Disco-2 (ONE-TIME, DONE: B01-B16 ingested
                   2026-09-30..10-02; tasks/drives_ingest_dryrun_review.md, the runbook
                   tasks/drives_microscopy_ingest_runbook.md). Its plan is FROZEN and its inputs (the
                   staged drives on D:) were erased on 2026-10-05: `plan` cannot run again for it; the
                   other commands still read its frozen expected.csv.
  drive3_2026-10   M. Jesus's drive (MJesus-MFB, WD WX22D623YP29), staged read-only on
                   J:\\_staging_drive3_MJ\\. Stream C: the Cell Observer .czi production lacks
                   (tasks/drive3_czi_gate.md). Inputs: part A1's per-file header table
                   (a1\\microscopy_files.csv, the catalog's own .czi reader + device fingerprint), part
                   A2's per-file claims (the drives claims engine, unchanged, run over drive 3), the drive
                   manifest, and a fresh production hash index (catalog.py production --out ...).

    python tools/drive_staging/ingest_plan.py [--profile P] goptical [--hash]   # ZWSI only (drives 1+2)
    python tools/drive_staging/ingest_plan.py [--profile P] plan                 # -> <out>\\expected.csv ...
    python tools/drive_staging/ingest_plan.py [--profile P] extract              # archive-only .czi (drives 1+2)
    python tools/drive_staging/ingest_plan.py [--profile P] localize             # drive 3: J: -> local mirror on D:
    python tools/drive_staging/ingest_plan.py [--profile P] verify-local         # drive 3: re-hash the mirror vs the manifest
    python tools/drive_staging/ingest_plan.py [--profile P] farm [--batch B01]   # hard-link farm
    python tools/drive_staging/ingest_plan.py [--profile P] configs              # -> tools/configs/<profile dir>/
    python tools/drive_staging/ingest_plan.py [--profile P] scratch --batch B01  # rehearsal NAS root (never J:)

WHAT IS IN SCOPE: every DISTINCT .czi content (by sha256) that is class `czi-raw`, whose device
fingerprint is one of the profile's instruments (drives 1+2: CELL / LSM9 / ZWSI / the external Axio
Imager -> XMIC; drive 3: CELL only -- its Axioscan 7 #4661000340 and Leica SP8 are not gjesus3's and wait
on M. Jesus, the Charite XMIC precedent), whose bytes are not already in production, and -- for ZWSI --
not already in the AxioScan's own archive on S:\\goptical. Contents only inside an archive are in scope
too (drives 1+2: extracted, then farmed).

ONE CANONICAL COPY PER CONTENT, first rule that separates wins: (1) its claim gives a project; (2) a
loose copy outside the profile's deprioritised top folders (drives 1+2: the Toshiba backup; drive 3:
`biomaGUNE MJ`, Ryan's "last"), then a loose copy inside them, then an archive member; (3) a non-blank
researcher; (4) the shorter path; (5) the drives in profile order; (6) lexicographic. Copies that claim
DIFFERENT projects are a conflict: listed in conflicts.csv, blank project.

PER-FILE VALUES (Ryan, 2026-09-29): instrument = fingerprint, never the folder. Project = the claim's
AE-biomaGUNE-NNNN for Confirmed and (A); blank for (C) and no-claim. Subject id = the claims table's,
Confirmed only. Researcher = the innermost person folder as written, EXCEPT under the profile's
operator top folders (drives 1+2: `Cell observer\\AINHIZE|Marta`, `CELL OBSERVER 2\\AINHIZE|Marta`),
which give the OPERATOR; elsewhere the operator is blank. czi_user is never used; initials are never
mapped to people. data_source internal (XMIC `collaborator:Charite`). original_name =
`<drive-label>/<source relpath>` -- the farm is laid out so that the engine derives exactly that.

THE SAME ACQUISITION UNDER DIFFERENT BYTES (gate 2026-09-30, rules R1-R4): ZEN rewrites a .czi when
display settings, a scale bar or pyramids are saved, so (instrument, acquisition second, file name)
identifies the acquisition, not the sha256. drives 1+2 applied R1-R3 by rule and kept every R4 group
member in /raw/ (flagged; derivatives were retired later, tasks/drives_r4_cleanup_review.md). drive 3
decides BEFORE ingest: a re-save of a production acquisition within RESAVE_SIZE_TOL is dropped (R1);
every other file that shares an (instrument, acquisition second) with another planned file or with a
production acquisition goes through the drives' tile-by-tile pixel check
(tools/drive_staging/drive3/c_groups.py, r4_groups.py's tests) and is kept, dropped as a re-save, or
routed to the project folder as non-raw material (Ryan, 2026-10-01), group by group
(`same_acquisition_actions`). A group the pixel check has not decided keeps the plan from passing.

Writes only under the profile's out / farm / extract / local folders and the repo config folder. Never
writes under a staged drive tree (drive 3: J:\\_staging_drive3_MJ\\ is only read) or under the NAS root.
"""
import argparse
import collections
import concurrent.futures as cf
import csv
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
REPO = os.path.dirname(TOOLS)
sys.path.insert(0, HERE)
from stage_copy import CHUNK, keep_awake, longpath, load_manifest  # noqa: E402

csv.field_size_limit(2 ** 31 - 1)

NAS = r"J:\gjesus3-data"
GOPTICAL = r"S:\goptical\GOpticalUsers data\AxioScan"
SEVENZIP = r"C:\Program Files\7-Zip\7z.exe"
MFB_RE = re.compile(r"^MFB[_-]([A-Za-z]+)[_-]([^_]+)[_-]([^_]+)[_-]")
XMIC_MODEL = "Axio Imager.Z2"            # rebound per profile (use_profile): the external microscope's model,
XMIC_SOURCE = "collaborator:Charite"      # written literally, and its data_source
RESAVE_SIZE_TOL = 150_000      # bytes: a same-size twin is a plain re-save
# characters: the engine globs and opens farm files WITHOUT the \\?\ prefix, and LongPathsEnabled is 0 on
# the workstation, so a farm file path must stay within MAX_PATH (260 with the terminating NUL = 259
# characters; one spare). Drive 3's deepest is 256 (directory part 225, under CreateDirectory's 248).
MAX_FARM_PATH = 258

# ---------------------------------------------------------------------------------------------
# drives 1+2: decisions recorded by hand at the 2026-09-30 gate (tile-by-tile pixel comparison
# with czifile). Any new one stops their plan until it is looked at.
# ---------------------------------------------------------------------------------------------
_D12_RESAVE_DECISIONS = {
    # 4h_HepG2_LP-IONP_20X_6.czi vs ACQ-20230726-CELL-037: pixels identical (3x520x692); production
    # is 0.5 MB LARGER (extra saved metadata) -> a re-save; drop.
    "44f35a6eb91ff0081a1ee99e5839ed0ee4dacabed2f98a720c6423e36b32cc3a": "drop",
    # ID59_1022_tumor_CD206.czi vs ACQ-20251031-CELL-003: the PRODUCTION copy is truncated (5.1 MB
    # short; tile 108 of 108 unreadable, "failed to read 9348144 bytes, got 4267924"); the drive copy
    # is complete and its other 107 tiles are identical. Same acquisition, so not a new ACQ-ID: HOLD
    # it and report -- the repair is to replace production's primary (recovery pattern).
    # REPAIRED 2026-10-01 (tools/repair_primary_inplace.py): production now holds these bytes.
    "dc8e8fe75a7356ee8ad229d3b329ed5ebff72dfcaca6bf7555f1bea0dd2bc497": "hold-production-truncated",
}
# Same (instrument, timestamp) as a production acquisition, different name (R3), inspected:
_D12_DERIVED_DECISIONS = {
    # the four `...Scale...` Cell Observer files: pixels identical to their production parent
    # (checked 2026-09-30); a scale-bar annotation re-save -> a derivative, not raw.
    "e0093b162dd099707a867d2ae4059686eed23899b5e058cd1dfdf1fdc25220a8": "scale-bar copy, pixels identical",
    "4f00e31a7dd281da81468dad6bd1b79de322efce044ec5af117304f1ee5977c0": "scale-bar copy, pixels identical",
    "1ef3b08a63ff20d383108ca2abbf6a736c1f4ee50cf058131347bee8e4a99fd1": "scale-bar copy, pixels identical",
    "ca458e8fd82210701b35487f322a6e9f8f0ed3843f9d282c6ab0af65e12eb59e": "scale-bar copy, pixels identical",
}

_D12_NOTE = ("Historical drive ingest 2026 ({label}); project / researcher / operator / subject decided "
             "per file before ingest (tasks/drives_ingest_dryrun_review.md). Claim: {claim}.")
_D3_NOTE = ("Historical drive ingest 2026 ({label}); project / researcher / operator / subject decided "
            "per file before ingest (tasks/drive3_czi_gate.md). Claim: {claim}.")

D3_ANALYSIS = r"D:\projects\gjesus3\drive3_analysis"
D3_STREAM = r"D:\projects\gjesus3\drive3_streams\czi"
D3X_STREAM = r"D:\projects\gjesus3\drive3_streams\xmic"
# drive 3's Biodonostia Axioscan (tasks/drive3_foreign_raw_gate.md): Irene's answer of 2026-10-08 (question 9) is
# recorded on every row, since the operator field stays blank (no folder names her, and her surname is unknown).
_D3X_NOTE = ("Historical drive ingest 2026 ({label}); external instrument: ZEISS Axioscan 7 #4661000340 at "
             "Biodonostia, where Elena (a PhD student of the group co-supervised at Biodonostia; surname not "
             "recorded) scanned M. Jesus's slides, with no formal collaboration (Irene, 2026-10-08); "
             "project / subject decided per file before ingest (tasks/drive3_foreign_raw_gate.md). Claim: {claim}.")

PROFILES = {
    "drives_2026-09": {
        "title": "Historical microscopy drives FRIO-X6 + MFB-Disco-2",
        "staging": r"D:\projects\gjesus3\staging",
        "cat": r"D:\projects\gjesus3\staging\_analysis\catalog",
        "codes": r"D:\projects\gjesus3\staging\_analysis\codes",
        "out": r"D:\projects\gjesus3\staging\_analysis\ingest",
        "farm": r"D:\projects\gjesus3\staging\_farm",
        "extract": r"D:\projects\gjesus3\staging\_extract",
        "local": "",                     # the farm links the staged copies directly (same volume)
        "manifest": "",
        "a1_files": "",
        "config_dir_rel": "tools/configs/drives_2026-09",
        "config_prefix": "drives_",
        "batch_prefix": "B",
        "batch_cap": 400 * 10**9,
        "scratch_root": r"D:\projects\gjesus3\scratch_nas",
        # catalog drive -> (claims drive, farm label == first component of original_name, staged folder)
        "drives": {
            "D1": ("drive1", "drive1_FRIO-X6", "drive1_FRIO-X6_2322E4A111E7"),
            "D2": ("drive2", "drive2_MFB-Disco-2", "drive2_MFB-Disco-2_2322E4A112BD"),
        },
        "instruments": {"CELL": "CELL", "LSM9": "LSM9", "ZWSI": "ZWSI", "EXTERNAL:AxioImagerZ2": "XMIC"},
        "deprioritised_tops": ("2025-10-02 - Toshiba EXT (Backup)",),
        # (drive, top folder, operator folder) -- matched case-insensitively, recorded as written
        "operator_tops": {("D1", "cell observer", "ainhize"), ("D1", "cell observer", "marta"),
                          ("D2", "cell observer 2", "ainhize"), ("D2", "cell observer 2", "marta")},
        "new_project": "AE-biomaGUNE-0118",      # the only project this ingest creates
        "xmic_expected": 338,
        "note": _D12_NOTE,
        "a_claim_text": "A (118 -> 0118; subject HELD until confirmed)",
        "resave_decisions": _D12_RESAVE_DECISIONS,
        "derived_decisions": _D12_DERIVED_DECISIONS,
        "same_acq_mode": "flag",          # R4: keep every member, flag it (the 2026-09-30 gate)
        "provenance": "tasks/drives_ingest_provenance.csv",
        "review_doc": "tasks/drives_ingest_dryrun_review.md",
        "runbook": "tasks/drives_microscopy_ingest_runbook.md",
    },
    "drive3_2026-10": {
        "title": "M. Jesus's drive (MJesus-MFB, WD WX22D623YP29): the Cell Observer .czi production lacks",
        "staging": r"J:\_staging_drive3_MJ",     # READ-ONLY: never written by any command
        "cat": os.path.join(D3_STREAM, "catalog"),
        "codes": os.path.join(D3_ANALYSIS, "a2", "claims"),
        "out": os.path.join(D3_STREAM, "plan"),
        "farm": os.path.join(D3_STREAM, "farm"),
        "extract": os.path.join(D3_STREAM, "_extract_unused"),
        "local": os.path.join(D3_STREAM, "local"),
        "manifest": os.path.join(D3_ANALYSIS, "drive3_manifest.csv"),
        "a1_files": os.path.join(D3_ANALYSIS, "a1", "microscopy_files.csv"),
        "config_dir_rel": "tools/configs/drives3_2026-10",
        "config_prefix": "drives3_",
        "batch_prefix": "C",
        "batch_cap": 250 * 10**9,
        "scratch_root": os.path.join(D3_STREAM, "rehearsal_nas"),
        "drives": {"D3": ("drive3", "drive3_MJesus-MFB", "drive3_MJesus_WX22D623YP29")},
        "instruments": {"CELL": "CELL"},
        "deprioritised_tops": ("biomaGUNE MJ",),
        "operator_tops": set(),
        # The coordinator's G5 ruling (2026-10-06): a folder that names its person gives that field, with the
        # token production already uses -- `Marta` (912 drives 1+2 rows, the 2026-09-29 rule) and `MJ` (stream N's
        # token for this drive). Applied to the CANONICAL copy after it is chosen, so no canonical choice moves.
        "people_by_folder": (
            ("Microscopio\\CELL OBS MARTA\\", "operator", "Marta"),
            ("Microscopio\\Microscopio- MJesus Sanchez 2023\\", "researcher", "MJ"),
        ),
        "new_project": None,              # this ingest creates no project
        "xmic_expected": None,
        "note": _D3_NOTE,
        "a_claim_text": "",
        "resave_decisions": {},           # drive 3 records its decisions in pixel_decisions.csv
        "derived_decisions": {},
        "same_acq_mode": "decide",
        "provenance": "tasks/drive3_czi_ingest_provenance.csv",
        "review_doc": "tasks/drive3_czi_gate.md",
        "runbook": "tasks/drive3_czi_gate.md",
    },
    # The same drive's scans from Biodonostia's Axioscan 7 #4661000340, as XMIC (the Charite precedent of drives
    # 1+2). Stream C's inputs and rules, unchanged; what differs is the instrument (A1's table predates the
    # reference entry, so its rows are re-fingerprinted against the reference: `refingerprint`), the XMIC model and
    # source, the note, the pilot's size, and the same-acquisition facts: these files are stored JPEG XR
    # compressed, which c_groups.py refuses, so the facts come from drive3/x_groups.py (stored tile payloads).
    "drive3x_2026-10": {
        "title": "M. Jesus's drive (MJesus-MFB, WD WX22D623YP29): the Biodonostia Axioscan 7 scans, as XMIC",
        "staging": r"J:\_staging_drive3_MJ",     # READ-ONLY: never written by any command
        "cat": os.path.join(D3X_STREAM, "catalog"),
        "codes": os.path.join(D3_ANALYSIS, "a2", "claims"),
        "out": os.path.join(D3X_STREAM, "plan"),
        "farm": os.path.join(D3X_STREAM, "farm"),
        "extract": os.path.join(D3X_STREAM, "_extract_unused"),
        "local": os.path.join(D3X_STREAM, "local"),
        "manifest": os.path.join(D3_ANALYSIS, "drive3_manifest.csv"),
        "a1_files": os.path.join(D3_ANALYSIS, "a1", "microscopy_files.csv"),
        "config_dir_rel": "tools/configs/drives3x_2026-10",
        "config_prefix": "drives3x_",
        "batch_prefix": "X",
        "batch_cap": 250 * 10**9,
        "scratch_root": os.path.join(D3X_STREAM, "rehearsal_nas"),
        "drives": {"D3": ("drive3", "drive3_MJesus-MFB", "drive3_MJesus_WX22D623YP29")},
        "instruments": {"EXTERNAL:Axioscan7-Biodonostia": "XMIC"},
        "refingerprint": True,
        "deprioritised_tops": ("biomaGUNE MJ",),
        "operator_tops": set(),
        "people_by_folder": (),           # no folder here names a person
        # Ryan, 2026-10-08 (via the coordinator), on Irene's answer ("Elena performed these scans with MJ's samples"):
        # researcher = M. Jesus on every file, with the token production already uses for her on this drive (`MJ`:
        # stream C's 3,719 Cell Observer rows, stream N's PET/CT). The operator stays blank; the note names Elena.
        "people_all": (("researcher", "MJ"),),
        "new_project": None,
        "xmic_expected": 83,
        "xmic_model": "Axioscan 7",       # the stand name the file carries (as production's ZWSI rows)
        "xmic_source": "collaborator:Biodonostia",
        "pilot": {"per_project": 1, "per_project_no_subject": 1, "no_project": 2, "flagged": 2, "deepest": 1},
        "note": _D3X_NOTE,
        "a_claim_text": "",
        "resave_decisions": {},
        "derived_decisions": {},
        "same_acq_mode": "decide",
        "provenance": "tasks/drive3_foreign_raw_ingest_provenance.csv",
        "review_doc": "tasks/drive3_foreign_raw_gate.md",
        "runbook": "tasks/drive3_foreign_raw_gate.md",
    },
}
DEFAULT_PROFILE = "drives_2026-09"
PROFILE_NAME = None
PROFILE = None
# the pilot batch (pilot_selection): per project, the smallest files with a subject link and without; the smallest
# files with no project; the smallest same-acquisition groups (members); the deepest farm paths. A profile may
# shrink it ("pilot"): stream C's pilot was 42 small files, an Axioscan file is 0.3-3 GB.
PILOT_DEFAULT = {"per_project": 4, "per_project_no_subject": 2, "no_project": 8, "flagged": 6, "deepest": 6}
PILOT = dict(PILOT_DEFAULT)


def use_profile(name):
    """Bind the module constants to one profile. Every command and the sibling tools call this first."""
    global PROFILE_NAME, PROFILE, STAGING, CAT, CODES, OUT, FARM, EXTRACT, LOCAL, MANIFEST, A1_FILES
    global CONFIG_DIR, CONFIG_DIR_REL, CONFIG_PREFIX, BATCH_PREFIX, BATCH_CAP, SCRATCH_ROOT, DRIVES
    global INSTRUMENTS, DEPRIORITISED_TOPS, BACKUP_TOP, OPERATOR_TOPS, NEW_PROJECT, NOTE
    global RESAVE_DECISIONS, DERIVED_DECISIONS, SAME_ACQ_MODE, PROVENANCE, DRIVE_ORDER, PEOPLE_BY_FOLDER
    global XMIC_MODEL, XMIC_SOURCE, PILOT
    if name not in PROFILES:
        raise SystemExit(f"unknown profile {name!r}; known: {sorted(PROFILES)}")
    p = PROFILES[name]
    PROFILE_NAME, PROFILE = name, p
    STAGING, CAT, CODES, OUT = p["staging"], p["cat"], p["codes"], p["out"]
    FARM, EXTRACT, LOCAL = p["farm"], p["extract"], p["local"]
    MANIFEST, A1_FILES = p["manifest"], p["a1_files"]
    CONFIG_DIR_REL, CONFIG_PREFIX = p["config_dir_rel"], p["config_prefix"]
    CONFIG_DIR = os.path.join(REPO, *CONFIG_DIR_REL.split("/"))
    BATCH_PREFIX, BATCH_CAP, SCRATCH_ROOT = p["batch_prefix"], p["batch_cap"], p["scratch_root"]
    DRIVES, DRIVE_ORDER = p["drives"], list(p["drives"])
    INSTRUMENTS = p["instruments"]
    DEPRIORITISED_TOPS = p["deprioritised_tops"]
    BACKUP_TOP = DEPRIORITISED_TOPS[0]
    OPERATOR_TOPS, NEW_PROJECT, NOTE = p["operator_tops"], p["new_project"], p["note"]
    PEOPLE_BY_FOLDER = p.get("people_by_folder", ())
    RESAVE_DECISIONS, DERIVED_DECISIONS = p["resave_decisions"], p["derived_decisions"]
    SAME_ACQ_MODE, PROVENANCE = p["same_acq_mode"], p["provenance"]
    XMIC_MODEL = p.get("xmic_model", "Axio Imager.Z2")
    XMIC_SOURCE = p.get("xmic_source", "collaborator:Charite")
    PILOT = dict(PILOT_DEFAULT, **p.get("pilot", {}))
    return p


use_profile(DEFAULT_PROFILE)


def config_file(batch):
    """The generated config of one batch (repo-relative form, as registry_raw.ingest_config holds it)."""
    return f"{CONFIG_DIR_REL}/{CONFIG_PREFIX}{batch}.yaml"


def rcsv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)


def wcsv(path, cols, rows):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    os.replace(tmp, path)


def gb(n):
    return round(n / 1e9, 1)


def staged_path(drive, relpath):
    return os.path.join(STAGING, DRIVES[drive][2], "files", relpath)


def local_path(relpath):
    """The local mirror copy of a staged file (drive 3: J: is copied once to D:, verified)."""
    return os.path.join(LOCAL, relpath)


def archive_key(drive, archive_relpath):
    """Folder name under _extract\\ for one archive: short, unique, readable."""
    base = archive_relpath.split("\\")[-1]
    h = hashlib.sha1(f"{drive}|{archive_relpath}".encode("utf-8")).hexdigest()[:6]
    return f"{drive}_{h}_{base}"


def in_deprioritised(path):
    """Is this copy under one of the profile's deprioritised top folders (canonical rule 2)?"""
    return any(path.startswith(t + "\\") for t in DEPRIORITISED_TOPS)


# ---------------------------------------------------------------------------------------------
# goptical: which ZWSI are already in the AxioScan's own archive (drives 1+2)
# ---------------------------------------------------------------------------------------------

def sha256_file(path):
    h = hashlib.sha256()
    with open(longpath(path), "rb") as f:
        for b in iter(lambda: f.read(CHUNK), b""):
            h.update(b)
    return h.hexdigest()


def cmd_goptical(args):
    os.makedirs(args.out, exist_ok=True)
    rows = []
    for root, _dirs, files in os.walk(GOPTICAL):
        for fn in files:
            if fn.lower().endswith(".czi"):
                p = os.path.join(root, fn)
                rows.append({"name": fn, "size": os.path.getsize(p), "path": p, "sha256": ""})
    print(f"{len(rows)} .czi under {GOPTICAL}")
    idx_path = os.path.join(args.out, "goptical_index.csv")
    if args.hash:
        # hash only the files that match an in-scope ZWSI by (name, size): cheap, and it is proof
        prod = {r["sha256"] for r in rcsv(os.path.join(CAT, "production_hashes.csv"))}
        want = set()
        for r in rcsv(os.path.join(CAT, "files.csv")):
            if r["instrument"] == "ZWSI" and r["class"] == "czi-raw" and r["sha256"] not in prod:
                want.add((r["relpath"].split("\\")[-1].lower(), int(r["size"])))
        for r in rows:
            if (r["name"].lower(), r["size"]) in want:
                r["sha256"] = sha256_file(r["path"])
        print(f"hashed {sum(1 for r in rows if r['sha256'])} candidate matches")
    wcsv(idx_path, ["name", "size", "path", "sha256"], rows)
    print(f"-> {idx_path}")


# ---------------------------------------------------------------------------------------------
# plan: shared rules
# ---------------------------------------------------------------------------------------------

def person_fields(drive, path_parts, old_researcher):
    """(researcher, operator) under the 2026-09-29 rule. path_parts = the loose relpath (or the
    archive's relpath) split on backslash."""
    if len(path_parts) >= 3 and (drive, path_parts[0].lower(), path_parts[1].lower()) in OPERATOR_TOPS:
        op = path_parts[1]
        researcher = "" if old_researcher.strip().lower() == op.lower() else old_researcher
        return researcher, op
    return old_researcher, ""


def canon_key(c, strict=False):
    """Sort key: the canonical copy of one content sorts first (rules in the module docstring).
    Rule 2 is three-valued -- loose outside the deprioritised tops, loose inside them, archive member --
    so a loose copy is preferred to an extraction when the rule's own two values tie; `strict` is the
    rule exactly as written (two values), kept to report whether the refinement ever changed a pick."""
    if strict:
        loc = 0 if c["kind"] == "loose" and not c["in_backup"] else 1
    else:
        loc = 0 if c["kind"] == "loose" and not c["in_backup"] else 1 if c["kind"] == "loose" else 2
    order = DRIVE_ORDER.index(c["drive"]) if c["drive"] in DRIVE_ORDER else len(DRIVE_ORDER)
    return (0 if c["project"] else 1, loc, 0 if c["researcher"] else 1, len(c["path"]), order, c["path"])


# ---------------------------------------------------------------------------------------------
# Gate rules R1-R4 (coordinator gate 2026-09-30): the same ACQUISITION under different bytes.
# ZEN rewrites a .czi when display settings, annotations (a scale bar) or pyramids are saved, so the
# sha256 differs and content dedup passes it through. The acquisition timestamp (to the second) is
# written at acquisition and survives a re-save; with the instrument and the filename it identifies
# the acquisition.
# ---------------------------------------------------------------------------------------------

ROI_LOBULO_RE = re.compile(r"_ROI lobulo \d+\.czi$", re.I)   # the 18 ZWSI per-lobe crops (gate G2/R3)
NONRAW_COLS = ["sha256", "instrument", "size", "original_name", "drive", "relpath", "why",
               "parent_acq_ids", "parent_original_names", "parent_project_ids", "destination_project",
               "acquisition_datetime"]
GROUP_NOTE = ("shares its acquisition timestamp with {m} other file{s} in this ingest (likely a ZEN scene "
              "split, stitched copy or extract)")


def _base(p):
    return p.replace("\\", "/").split("/")[-1].lower()


def resave_key(inst, adt, name):
    return (inst, (adt or "")[:19], _base(name))


def production_index(nas):
    """(instrument, ts19, basename) -> [rows] and (instrument, ts19) -> [rows] from registry_raw."""
    by_key, by_ts = collections.defaultdict(list), collections.defaultdict(list)
    for r in rcsv(os.path.join(nas, "registries", "registry_raw.csv")):
        ts = r["acquisition_datetime"][:19]
        if len(ts) < 19:
            continue
        by_key[resave_key(r["instrument"], ts, r["original_name"])].append(r)
        by_ts[(r["instrument"], ts)].append(r)
    return by_key, by_ts


def apply_gate_rules(expected, excluded, conflicts, nas):
    """drives 1+2 (same_acq_mode 'flag'): R1-R3 by rule and hand-recorded decision, R4 flagged."""
    by_key, by_ts = production_index(nas)
    kept, nonraw = [], []
    # R1 -- a re-save of a production acquisition
    for e in expected:
        twins = by_key.get(resave_key(e["instrument"], e["acquisition_datetime"], e["original_name"]))
        if not twins:
            kept.append(e)
            continue
        if len(twins) > 1:
            raise SystemExit(f"R1: {e['original_name']} matches {len(twins)} production rows")
        t = twins[0]
        prim = os.path.join(nas, t["canonical_path"].strip("/").replace("/", "\\"), t["primary_file_name"])
        diff = int(e["size"]) - os.path.getsize(prim)
        decision = "drop" if abs(diff) <= RESAVE_SIZE_TOL else RESAVE_DECISIONS.get(e["sha256"])
        if decision is None:
            raise SystemExit(f"R1: {e['original_name']} vs {t['acq_id']} differs by {diff} bytes and has "
                             f"no recorded decision: inspect it and add it to RESAVE_DECISIONS")
        reason = (f"resave-of-production:{t['acq_id']}" if decision == "drop"
                  else f"production-copy-truncated:{t['acq_id']} (drive copy complete; HOLD, repair production)")
        excluded.append({"sha256": e["sha256"], "instrument": e["instrument"], "size": e["size"],
                         "reason": reason.split(":")[0], "detail": reason + f"; size diff {diff} B",
                         "copies": e["n_copies"], "path": e["original_name"]})
    expected, kept = kept, []
    # R3 -- same (instrument, timestamp) as a production acquisition under another name
    for e in expected:
        parents = by_ts.get((e["instrument"], e["acquisition_datetime"][:19]))
        if not parents:
            kept.append(e)
            continue
        base = e["original_name"].split("/")[-1]
        if e["instrument"] == "ZWSI" and ROI_LOBULO_RE.search(base):
            why = "per-lobe ROI crop of an AxioScan scan (same timestamp), folder 'Prueba jpeg'"
        elif e["sha256"] in DERIVED_DECISIONS:
            why = DERIVED_DECISIONS[e["sha256"]]
        else:
            raise SystemExit(f"R3: {e['original_name']} shares its timestamp with "
                             f"{[p['acq_id'] for p in parents]}: inspect it and record a decision")
        nonraw.append({"sha256": e["sha256"], "instrument": e["instrument"], "size": e["size"],
                       "original_name": e["original_name"], "drive": e["drive"], "relpath": e["relpath"],
                       "why": why, "parent_acq_ids": ";".join(p["acq_id"] for p in parents),
                       "parent_original_names": ";".join(p["original_name"] for p in parents),
                       "parent_project_ids": ";".join(sorted({p["project_id"] for p in parents if p["project_id"]})),
                       "destination_project": e["project"],
                       "acquisition_datetime": e["acquisition_datetime"]})
        excluded.append({"sha256": e["sha256"], "instrument": e["instrument"], "size": e["size"],
                         "reason": "derivative-of-production", "detail": why + "; parents "
                         + ";".join(p["acq_id"] for p in parents) + "; -> nonraw_derived.csv",
                         "copies": e["n_copies"], "path": e["original_name"]})
    expected = kept
    # R2 -- re-saves within the plan: one canonical per (instrument, ts19, filename)
    groups = collections.defaultdict(list)
    for e in expected:
        groups[resave_key(e["instrument"], e["acquisition_datetime"], e["original_name"])].append(e)
    kept = []
    for key, es in groups.items():
        es.sort(key=lambda e: canon_key(e["_c"]))
        keep = es[0]
        if len(es) > 1:
            real = sorted({e["project"] for e in es if e["project"]})
            if len(real) > 1:
                conflicts.append({"sha256": keep["sha256"], "instrument": keep["instrument"],
                                  "projects": ";".join(real), "canonical": keep["original_name"],
                                  "copies": "R2 re-save group: " + " | ".join(e["original_name"] for e in es)})
                keep.update(project="", subject_id="", subject_alias="", subject_animal="",
                            verdict="CONFLICT", sample_type="")
            extra = []
            for e in es[1:]:
                extra.append(e["original_name"])
                if e["other_copies"]:
                    extra.append(e["other_copies"])
                excluded.append({"sha256": e["sha256"], "instrument": e["instrument"], "size": e["size"],
                                 "reason": "resave-within-plan",
                                 "detail": f"same instrument/timestamp/filename as kept {keep['sha256'][:12]} "
                                           f"({keep['original_name']}); size diff "
                                           f"{int(e['size']) - int(keep['size'])} B",
                                 "copies": e["n_copies"], "path": e["original_name"]})
            keep["other_copies"] = ";".join(x for x in [keep["other_copies"]] + extra if x)
            keep["n_copies"] = int(keep["n_copies"]) + sum(int(e["n_copies"]) for e in es[1:])
            keep["resave_group_n"] = len(es)
        kept.append(keep)
    expected = kept
    # R4 -- still-distinct files sharing (instrument, full timestamp): keep all, make them findable
    ts_groups = collections.defaultdict(list)
    for e in expected:
        ts_groups[(e["instrument"], e["acquisition_datetime"])].append(e)
    for (inst, adt), es in ts_groups.items():
        n = len(es)
        for e in es:
            e["acq_group"] = f"{inst}|{adt}" if n > 1 else ""
            e["acq_group_n"] = str(n) if n > 1 else ""
            if n > 1:
                e["notes"] = e["notes"].rstrip(".") + "; " + GROUP_NOTE.format(m=n - 1, s="" if n == 2 else "s") + "."
    return expected, nonraw


# ---------------------------------------------------------------------------------------------
# drive 3 (same_acq_mode 'decide'): every same-acquisition group decided by the pixel check BEFORE
# ingest. The pixel check (drive3/c_groups.py) reports facts per member -- class, parent, evidence,
# whether every tile is complete -- and same_acquisition_actions() applies Ryan's rule to them.
# ---------------------------------------------------------------------------------------------

C_ORIGINAL, C_DISTINCT, C_AMBIGUOUS = "original", "distinct", "ambiguous"
C_SCALEBAR, C_RESAVE, C_SUBSET = "scale-bar copy", "identical re-save", "export: subset"
IDENTICAL_CLASSES = (C_SCALEBAR, C_RESAVE)
ROOT_CLASSES = (C_ORIGINAL, C_DISTINCT, C_AMBIGUOUS)
PIXEL_CAND_COLS = ["group", "member", "role", "sha256", "acq_id", "path", "size", "name", "project",
                   "original_name"]
DECISION_COLS = ["group", "member", "role", "sha256", "acq_id", "name", "size", "class", "parent", "parent_name",
                 "via", "evidence", "complete", "complete_note", "has_scalebar", "creation_date",
                 "group_signature"]
NONRAW_D3_COLS = ["sha256", "instrument", "size", "original_name", "drive", "relpath", "class", "why",
                  "evidence", "parent_sha256", "parent_acq_id", "parent_original_name", "parent_project",
                  "own_claim_project", "destination_project", "destination_note", "acquisition_datetime"]
REPAIR_COLS = ["kind", "acq_id", "production_original_name", "production_size", "production_class",
               "production_complete", "drive_sha256", "drive_size", "drive_original_name", "drive_relpath",
               "evidence", "note"]
ACTION_KEEP, ACTION_FLAG, ACTION_DROP = "keep", "keep-flag", "drop-resave"
ACTION_NONRAW, ACTION_HOLD = "nonraw", "hold"
ACTION_UNDECIDED = "undecided"


def group_id(inst, adt):
    """A same-acquisition group: one instrument and one acquisition SECOND (the R1/R2/R3 resolution;
    a superset of drives 1+2's full-timestamp R4 groups and of the same-name re-save keys)."""
    return f"{inst}|{(adt or '')[:19]}"


def group_signature(member_ids):
    """Order-free fingerprint of a group's membership: a decision made for another membership is stale."""
    return hashlib.sha1("|".join(sorted(member_ids)).encode("utf-8")).hexdigest()[:16]


def same_acquisition_actions(plan_rows, prod_rows, decisions):
    """Decide every PLANNED member of ONE same-acquisition group (one instrument, one second).

    plan_rows:  planned files of the group (dicts with sha256, original_name, project, _c = the canonical
                copy, for canon_key).
    prod_rows:  production registry rows of the same instrument and second (acq_id, original_name,
                project_id): read-only parents, never acted on.
    decisions:  {member id: pixel-check row} -- member id = sha256 for a planned file, ACQ-ID for a
                production one; each row has class, parent (a member id), name, complete (Y/N) and the
                group_signature of the membership it was computed for. {} = not run yet.

    Returns {sha256: (action, parent member id, note)} for every planned row:
      keep         the acquisition (an original, or a distinct scene of it): /raw/
      keep-flag    /raw/, flagged: ambiguous; truncated with no complete twin; or production holds a
                   derivative of it under another name
      drop-resave  the same acquisition as the kept file or a production row (same name and second, and
                   pixel-identical, or a truncated copy of it): not ingested, its path kept in other_copies
      nonraw       a derivative (scale-bar copy or re-save under another name, crop, subset, scene split,
                   stitched copy, rendering): the original's project folder, as non-raw (Ryan, 2026-10-01)
      hold         a production row has this file's name and second (by the identity rule the same
                   acquisition) but holds a TRUNCATED copy, a DERIVATIVE, or other pixels: not a second ACQ-ID;
                   listed for the coordinator (a truncated or derivative primary is repaired from this file,
                   on approval: the drives 1+2 ACQ-20251031-CELL-003 precedent)
      undecided    the pixel check has not run on exactly this membership

    The same name and second is the same acquisition (gate R1/R2): among planned same-name twins the
    canonical rule (canon_key) picks the one kept, a complete file always before a truncated one."""
    want = {r["sha256"] for r in plan_rows} | {p["acq_id"] for p in prod_rows}
    sig = group_signature(want)
    if not decisions or set(decisions) != want or any(d.get("group_signature") != sig for d in decisions.values()):
        return {r["sha256"]: (ACTION_UNDECIDED, "", "the pixel check has not decided this membership")
                for r in plan_rows}
    plan = {r["sha256"]: r for r in plan_rows}
    cls = {m: d["class"] for m, d in decisions.items()}
    par = {m: d.get("parent", "") for m, d in decisions.items()}
    whole = {m: d.get("complete") == "Y" for m, d in decisions.items()}
    name = {m: _base(d["name"]) for m, d in decisions.items()}
    label = {m: d["name"] for m, d in decisions.items()}
    scalebar = {m: d.get("has_scalebar") == "True" for m, d in decisions.items()}
    roots = [m for m in decisions if cls[m] in ROOT_CLASSES]
    for m in decisions:
        if cls[m] not in ROOT_CLASSES and par[m] not in roots:
            return {r["sha256"]: (ACTION_UNDECIDED, "", f"pixel check: {label[m]} names no root as its parent")
                    for r in plan_rows}
    derived = {m for m in decisions if cls[m] not in ROOT_CLASSES and cls[m] not in IDENTICAL_CLASSES}
    out, done = {}, set()

    def tag(m):
        return f"production {m}" if m not in plan else label[m]

    # 1. under the acquisition's own name and second, production holds a truncated copy or a derivative of
    #    a planned file: the planned file is that acquisition, complete -- hold it for a repair, not a new id
    for p in decisions:
        r = par[p]
        if p not in plan and p in derived and r in plan and name[p] == name[r]:
            what = "a TRUNCATED copy" if not whole[p] else f"a {cls[p]}"
            out[r] = (ACTION_HOLD, p, f"production {p} holds {what} of this file under the same name and second: "
                                      "repair its primary from this file (on approval); no second ACQ-ID")
            done.add(r)
    # 1b. a planned truncated copy (incomplete subset) under the same name as its complete parent -- or (2026-10-08,
    #     the Biodonostia scans) as a complete pixel-identical copy of that parent: `2025_02_14__5234.czi` stops after
    #     1.46 of the 2.31 GB of the escaner copy of that name, a re-save of the root `ID1_0424_H+L.czi`
    for m in decisions:
        r = par[m]
        if not (m in plan and m in derived and not whole[m] and r in decisions and whole[r]):
            continue
        twins = [x for x in decisions if par[x] == r and cls[x] in IDENTICAL_CLASSES and whole[x]]
        same = [r] if name[r] == name[m] else [x for x in twins if name[x] == name[m]]
        if same:
            out[m] = (ACTION_DROP, r, f"a truncated copy of {tag(same[0])} (same name and second): the complete one "
                                      "is the acquisition")
            done.add(m)
    # 2. identical sets: a root and its pixel-identical copies; the kept member and its same-name re-saves.
    #    Among same-name twins the kept one is: a complete file; then, when the twins differ only by a
    #    scale-bar annotation layer, the CLEAN one (Ryan 2026-10-01: the acquisition is raw, a scale bar goes
    #    to the project folder); then the canonical rule (gate R2). An annotated same-name twin of a clean
    #    kept file is a scale-bar copy for the project folder; any other same-name twin is a plain re-save.
    keeper = {}
    for R in roots:
        S = [R] + [m for m in decisions if cls[m] in IDENTICAL_CLASSES and par[m] == R]
        prod_in = [m for m in S if m not in plan]
        if R not in plan:
            k = R
        elif prod_in:
            same = [m for m in prod_in if name[m] == name[R]]
            k = (same or prod_in)[0]
        else:
            cand = [m for m in S if name[m] == name[R] and m not in done]
            pool = [m for m in cand if whole[m]] or cand or [R]
            clean = [m for m in pool if not scalebar[m]]
            if clean and len(clean) < len(pool):
                pool = clean
            k = min(pool, key=lambda m: canon_key(plan[m]["_c"]))
        keeper[R] = k
        for m in S:
            if m not in plan or m in done or m == k:
                continue
            if name[m] == name[k] and scalebar[m] and not scalebar[k] and whole[m]:
                out[m] = (ACTION_NONRAW, k, f"a scale-bar copy of {tag(k)} under the same name (pixel-identical, "
                                            "an annotation layer added): the project folder")
            elif name[m] == name[k]:
                out[m] = (ACTION_DROP, k, f"same name and second, pixel-identical: a re-save of {tag(k)}"
                          + ("" if whole[m] else "; this copy is also truncated"))
            elif m == R and k not in plan and cls[k] == C_SCALEBAR:
                out[m] = (ACTION_FLAG, "", f"production {k} is a scale-bar copy of this file under another name; "
                                           "this file is the clean record of the acquisition")
            else:
                out[m] = (ACTION_NONRAW, k, f"{cls[m] if m != R else C_RESAVE} of {tag(k)} (pixel-identical, "
                                            "another name)" + ("" if whole[m] else "; truncated"))
        if k in plan and k not in out:
            if cls[R] == C_AMBIGUOUS:
                out[k] = (ACTION_FLAG, "", "ambiguous: " + (decisions[R].get("evidence") or
                                                             "the pixel check cannot tell which is the acquisition"))
            elif not whole[k]:
                out[k] = (ACTION_FLAG, "", "truncated, and no complete copy of it exists: kept as the only record, "
                                           "flagged")
            elif any(name[p] == name[k] for p in decisions if p not in plan):
                p = next(p for p in decisions if p not in plan and name[p] == name[k])
                if not whole[p]:
                    out[k] = (ACTION_HOLD, p, f"production {p} has this file's name and second but holds an "
                                              f"INCOMPLETE copy ({decisions[p].get('complete_note') or 'tiles missing'}): "
                                              "repair its primary from this file (on approval); no second ACQ-ID")
                else:
                    out[k] = (ACTION_HOLD, p, f"production {p} has this file's name and second (the same acquisition "
                                              "by the identity rule) but other pixels: held for the coordinator")
            else:
                out[k] = (ACTION_KEEP, "", cls[R])
    # 3. derivatives (crop, subset, scene split, stitched copy, rendering): the original's project folder
    for m in decisions:
        if m in plan and m not in out and m not in done:
            k = keeper[par[m]]
            out[m] = (ACTION_NONRAW, k, f"{cls[m]} of {tag(k)}" + ("" if whole[m] else "; truncated"))
    # 4. production holding a derivative of a planned file under ANOTHER name: the planned file is the
    #    acquisition (kept, flagged; the production row is reported)
    for p in derived:
        if p in plan:
            continue
        k = keeper.get(par[p], par[p])
        if k in plan and out.get(k, ("",))[0] in (ACTION_KEEP, ACTION_FLAG):
            out[k] = (ACTION_FLAG, "", f"production {p} is a {cls[p]} of this file: this file is the acquisition")
    for r in plan_rows:
        out.setdefault(r["sha256"], (ACTION_UNDECIDED, "", "no rule matched this member's evidence"))
    return out


# ---------------------------------------------------------------------------------------------
# plan
# ---------------------------------------------------------------------------------------------

def load_projects(nas):
    out = {}
    for r in rcsv(os.path.join(nas, "registries", "registry_projects.csv")):
        out[r["name"].strip().lower()] = {"project_id": r["project_id"].strip(), "name": r["name"].strip(),
                                          "status": r["status"].strip(),
                                          "folder": r["folder_location"].strip()}
    return out


def existing_links(nas, folder):
    d = os.path.join(nas, folder.strip("/").replace("/", "\\"), "raw_linked")
    try:
        return {n.lower() for n in os.listdir(d)}
    except FileNotFoundError:
        return set()


def assign_link_names(expected, projects, nas):
    """Link names unique per project, against what raw_linked\\ already holds (read-only listing):
    `<INST>_<file name>`, else `<INST>_<stem>_<YYYYMMDD><ext>`, else `..._<sha8>`."""
    taken = {}
    for e in sorted(expected, key=lambda e: e["original_name"]):
        base = e["original_name"].split("/")[-1]
        stem, ext = os.path.splitext(base)
        name = f"{e['instrument']}_{base}"
        if e["project"]:
            key = e["project"].lower()
            if key not in taken:
                p = projects.get(key)
                taken[key] = existing_links(nas, p["folder"]) if p else set()
            day = (e["acquisition_datetime"] or "")[:10].replace("-", "")
            for cand in (name, f"{e['instrument']}_{stem}_{day}{ext}",
                         f"{e['instrument']}_{stem}_{day}_{e['sha256'][:8]}{ext}"):
                if cand.lower() not in taken[key]:
                    name = cand
                    break
            else:
                raise SystemExit(f"no free link name for {e['original_name']}")
            taken[key].add(name.lower())
        e["link_name"] = name
    return expected


def cmd_plan(args):
    if PROFILE["same_acq_mode"] == "decide":
        return plan_drive3(args)
    return plan_drives_2026_09(args)


def plan_drives_2026_09(args):
    """drives 1+2. FROZEN at c5f7fff; its staged inputs were erased on 2026-10-05, so this runs no more."""
    os.makedirs(args.out, exist_ok=True)

    print("production hashes ...", file=sys.stderr)
    prod = {}
    for r in rcsv(os.path.join(CAT, "production_hashes.csv")):
        prod.setdefault(r["sha256"], r["acq_id"])
    reg_path = os.path.join(args.nas, "registries", "registry_raw.csv")
    with open(reg_path, encoding="utf-8-sig", newline="") as f:
        reg_rows = sum(1 for _ in csv.DictReader(f))
    ph_mtime = dt.datetime.fromtimestamp(os.path.getmtime(os.path.join(CAT, "production_hashes.csv")))

    print("claims ...", file=sys.stderr)
    fclaims = {(r["drive"], r["relpath"]): r for r in rcsv(os.path.join(CODES, "file_claims.csv"))}
    claim_token = {r["claim_id"]: r["token"] for r in rcsv(os.path.join(CODES, "claims.csv"))}

    print("catalog files ...", file=sys.stderr)
    copies = []
    tally = collections.Counter()
    out_classes = collections.defaultdict(lambda: [0, 0, set()])
    for r in rcsv(os.path.join(CAT, "files.csv")):
        ext = r["ext"].lower()
        if ext in (".tif", ".tiff", ".lsm"):
            k = out_classes[("loose", r["class"])]
            k[0] += 1
            k[1] += int(r["size"])
            k[2].add(r["sha256"])
            continue
        if ext != ".czi":
            continue
        tally[("czi", r["class"], r["instrument"])] += 1
        if r["class"] != "czi-raw" or r["instrument"] not in INSTRUMENTS:
            continue
        cdrive, label, _ = DRIVES[r["drive"]]
        cl = fclaims[(cdrive, r["relpath"])]
        parts = r["relpath"].split("\\")
        copies.append({
            "kind": "loose", "drive": r["drive"], "relpath": r["relpath"], "archive": "", "member": "",
            "path": r["relpath"], "parts": parts, "sha256": r["sha256"], "size": int(r["size"]),
            "instrument": INSTRUMENTS[r["instrument"]], "acq_dt": r["czi_acq_datetime"],
            "stand": r["czi_stand"], "claim": cl,
        })

    print("archive members ...", file=sys.stderr)
    members = []
    for r in rcsv(os.path.join(CAT, "archive_members.csv")):
        ext = r["ext"].lower()
        if ext in (".tif", ".tiff", ".lsm"):
            k = out_classes[("member", r["class"])]
            k[0] += 1
            k[1] += int(r["size"] or 0)
            k[2].add(r["sha256"])
            continue
        if ext != ".czi":
            continue
        tally[("czi-member", r["class"], r["instrument"])] += 1
        if r["class"] == "czi-raw" and r["instrument"] in INSTRUMENTS:
            members.append(r)
    member_archives = {(DRIVES[r["drive"]][0], r["archive_relpath"]) for r in members}
    mclaims = {}
    for r in rcsv(os.path.join(CODES, "archive_member_claims.csv")):
        if (r["drive"], r["archive_relpath"]) in member_archives:
            # 7-Zip lists .7z members with backslashes, zipfile with slashes: key on "/"
            mclaims[(r["drive"], r["archive_relpath"], r["member"].replace("\\", "/"))] = r
    for r in members:
        cdrive = DRIVES[r["drive"]][0]
        cl = mclaims.get((cdrive, r["archive_relpath"], r["member"].replace("\\", "/")))
        if cl is None:  # archive holds no member claims: the archive file's own row decides
            cl = dict(fclaims[(cdrive, r["archive_relpath"])])
            if cl["verdict"] == "ARCHIVE":
                raise SystemExit(f"member without a claim row in a claim-holding archive: {r}")
        path = r["archive_relpath"] + "\\" + r["member"].replace("/", "\\")
        copies.append({
            "kind": "member", "drive": r["drive"], "relpath": "", "archive": r["archive_relpath"],
            "member": r["member"], "path": path, "parts": r["archive_relpath"].split("\\"),
            "sha256": r["sha256"], "size": int(r["size"]),
            "instrument": INSTRUMENTS[r["instrument"]], "acq_dt": r["czi_acq_datetime"], "stand": "",
            "claim": cl,
        })

    # per-copy derived fields
    for c in copies:
        cl = c["claim"]
        verdict = cl["verdict"] or "NO-CLAIM"   # the claims tables write no-claim as blank
        c["verdict"] = verdict
        c["project"] = cl["proposed_project"] if verdict in ("CONFIRMED", "A") else ""
        c["subject_id"] = cl["subject_id"] if verdict == "CONFIRMED" else ""
        c["researcher"], c["operator"] = person_fields(c["drive"], c["parts"], cl["researcher"])
        c["in_backup"] = in_deprioritised(c["path"])
        c["claimed"] = claim_token.get(cl["claim_id"], "")
        c["conflict"] = cl["conflict"]

    # ---- group by content -------------------------------------------------------------------
    groups = collections.defaultdict(list)
    for c in copies:
        groups[c["sha256"]].append(c)

    # dup_groups.csv agreement: every in-scope content with >1 location is a dup group there
    dg = collections.Counter()
    for r in rcsv(os.path.join(CAT, "dup_groups.csv")):
        if r["sha256"] in groups:
            dg[r["sha256"]] += 1
    dup_mismatch = [s for s, cs in groups.items() if len(cs) > 1 and dg.get(s, 0) != len(cs)]
    dup_mismatch += [s for s in dg if len(groups[s]) != dg[s]]

    goptical = {}
    gi = os.path.join(args.out, "goptical_index.csv")
    if os.path.isfile(gi):
        for r in rcsv(gi):
            goptical.setdefault((r["name"].lower(), int(r["size"])), []).append(r)
    elif any(c["instrument"] == "ZWSI" for c in copies):
        raise SystemExit("run `ingest_plan.py goptical --hash` first (ZWSI check)")

    expected, excluded, conflicts = [], [], []
    strict_differs = 0
    for sha, cs in groups.items():
        insts = {c["instrument"] for c in cs}
        if len(insts) != 1:
            raise SystemExit(f"one content, two instruments: {sha} {insts}")
        inst = insts.pop()
        size = cs[0]["size"]
        # The engine discovers with glob, which never matches a name starting with "." -- such a
        # copy would sit in the farm and silently not ingest (found by the 2026-09-30 dry run).
        visible = [c for c in cs if not c["path"].split("\\")[-1].startswith(".")]
        if not visible:
            excluded.append({"sha256": sha, "instrument": inst, "size": size, "reason": "hidden-dotfile",
                             "detail": "name starts with '.': the engine's glob cannot see it; list for a one-off",
                             "copies": len(cs), "path": cs[0]["path"]})
            continue
        cs = visible
        if sha in prod:
            excluded.append({"sha256": sha, "instrument": inst, "size": size, "reason": "in-production",
                             "detail": prod[sha], "copies": len(cs), "path": min(cs, key=canon_key)["path"]})
            continue
        if inst == "ZWSI":
            c0 = min(cs, key=canon_key)
            hits = goptical.get((c0["path"].split("\\")[-1].lower(), size), [])
            same = [h for h in hits if h["sha256"] == sha]
            if same:
                excluded.append({"sha256": sha, "instrument": inst, "size": size,
                                 "reason": "in-goptical-axioscan", "detail": same[0]["path"],
                                 "copies": len(cs), "path": c0["path"]})
                continue
            if hits:
                raise SystemExit(f"ZWSI name+size match on S: with a different sha256: {c0['path']}")
        cs.sort(key=canon_key)
        canon = cs[0]
        if sorted(cs, key=lambda c: canon_key(c, strict=True))[0] is not canon:
            strict_differs += 1
        projects = sorted({c["project"] for c in cs if c["project"]})
        project, subject, verdict = canon["project"], canon["subject_id"], canon["verdict"]
        conflict_note = ""
        if len(projects) > 1:
            conflicts.append({"sha256": sha, "instrument": inst, "projects": ";".join(projects),
                              "canonical": canon["path"],
                              "copies": " | ".join(f"{c['drive']}:{c['path']} [{c['project'] or '-'}]" for c in cs)})
            project, subject, verdict = "", "", "CONFLICT"
            conflict_note = "copies claim " + " vs ".join(projects)
        subjects = {c["subject_id"] for c in cs if c["project"] == project and c["subject_id"]}
        if project and len(subjects) > 1:
            conflicts.append({"sha256": sha, "instrument": inst, "projects": project,
                              "canonical": canon["path"],
                              "copies": "subject ids disagree: " + ";".join(sorted(subjects))})
            subject = ""
            conflict_note = "copies name different subjects " + ";".join(sorted(subjects))
        label = DRIVES[canon["drive"]][1]
        base = canon["path"].split("\\")[-1]
        operator = canon["operator"]
        sample_id = base
        if inst == "ZWSI":
            m = MFB_RE.match(base)
            operator = m.group(1) if m else operator   # no initials (auto-named): the folder rule
            if m:
                sample_id = f"{m.group(2)}_{m.group(3)}"
        claim_txt = verdict if verdict != "C" else f"C (path claimed {canon['claimed'] or '?'}; left blank)"
        if verdict == "A":
            claim_txt = PROFILE["a_claim_text"]
        if verdict == "CONFLICT":
            claim_txt = f"conflict ({conflict_note}); left blank"
        alias = animal = ""
        if subject:
            m = re.fullmatch(r"(\d+)-AE-biomaGUNE-(\d{4})", subject)
            if not m:
                raise SystemExit(f"unexpected subject id {subject!r}")
            animal, alias = m.group(1), m.group(2)
        expected.append({
            "sha256": sha, "size": size, "instrument": inst, "kind": canon["kind"], "drive": canon["drive"],
            "relpath": canon["relpath"], "archive": canon["archive"], "member": canon["member"],
            "original_name": label + "/" + canon["path"].replace("\\", "/"),
            "acquisition_datetime": canon["acq_dt"], "czi_stand": canon["stand"],
            "project": project, "verdict": verdict, "claimed": canon["claimed"] if verdict == "C" else "",
            "researcher": canon["researcher"], "operator": operator, "subject_id": subject,
            "subject_alias": alias, "subject_animal": animal,
            "sample_id": sample_id, "sample_type": "tissue" if (subject or inst == "ZWSI") else "",
            "data_source": XMIC_SOURCE if inst == "XMIC" else "internal",
            "instrument_model": XMIC_MODEL if inst == "XMIC" else canon["stand"],
            "notes": NOTE.format(label=label, claim=claim_txt),
            "conflict": conflict_note or canon["conflict"],
            "n_copies": len(cs),
            "other_copies": ";".join(f"{DRIVES[c['drive']][1]}/{c['path'].replace(chr(92), '/')}" for c in cs[1:]),
            "_c": canon,
        })

    # ---- gate rules R1-R4 (2026-09-30): same acquisition under different bytes ------------------
    expected, nonraw = apply_gate_rules(expected, excluded, conflicts, args.nas)
    wcsv(os.path.join(args.out, "nonraw_derived.csv"), NONRAW_COLS, nonraw)

    # ---- projects ---------------------------------------------------------------------------------
    projects = load_projects(args.nas)
    for e in expected:
        p = projects.get(e["project"].lower()) if e["project"] else None
        e["project_id"] = p["project_id"] if p else ("NEW" if e["project"] else "")
        e["project_status"] = p["status"] if p else ("new" if e["project"] else "")
        if e["project"] and not p and e["project"] != NEW_PROJECT:
            raise SystemExit(f"project {e['project']} is not in production and is not {NEW_PROJECT}")

    # ---- batches ------------------------------------------------------------------------------------
    def bucket(e):
        if e["instrument"] != "CELL":
            return e["instrument"]
        if e["project"] == NEW_PROJECT:
            return "CELL-0118"
        if e["project_status"] == "closed":
            return "CELL-closed-" + e["project"][-4:]
        return "CELL-project" if e["project"] else "CELL-noproject"

    by_bucket = collections.defaultdict(list)
    for e in expected:
        by_bucket[bucket(e)].append(e)
    chunks = []
    for b, es in by_bucket.items():
        es.sort(key=lambda e: (e["project"], e["original_name"]))
        cur, size = [], 0
        for e in es:
            if cur and size + e["size"] > BATCH_CAP:
                chunks.append((b, cur))
                cur, size = [], 0
            cur.append(e)
            size += e["size"]
        chunks.append((b, cur))
    head = {"XMIC": 0, "CELL-0118": 1, "LSM9": 2, "ZWSI": 3}

    def order(ch):
        b, es = ch
        return (head.get(b, 5 if b.startswith("CELL-closed") else 4), sum(e["size"] for e in es))

    chunks.sort(key=order)
    batches = []
    for n, (b, es) in enumerate(chunks, 1):
        bid = f"{BATCH_PREFIX}{n:02d}"
        for e in es:
            e["batch"] = bid
        batches.append({"batch": bid, "bucket": b, "instrument": es[0]["instrument"], "files": len(es),
                        "gb": gb(sum(e["size"] for e in es)),
                        "projects": ";".join(sorted({e["project"] for e in es if e["project"]})) or "(none)",
                        "members": sum(1 for e in es if e["kind"] == "member"),
                        "auto_create": "Y" if b == "CELL-0118" else "N",
                        "needs_decision": "reopen closed project" if b.startswith("CELL-closed") else ""})

    # ---- link names: unique per project, against what raw_linked\ already holds ---------------------
    assign_link_names(expected, projects, args.nas)

    # ---- write -----------------------------------------------------------------------------------------
    cols = ["batch", "sha256", "size", "instrument", "kind", "drive", "relpath", "archive", "member",
            "original_name", "acquisition_datetime", "czi_stand", "instrument_model", "project",
            "project_id", "project_status", "verdict", "claimed", "researcher", "operator", "subject_id",
            "subject_alias", "subject_animal", "sample_id", "sample_type", "data_source", "link_name",
            "notes", "conflict", "n_copies", "other_copies", "acq_group", "acq_group_n", "resave_group_n"]
    expected.sort(key=lambda e: (e["batch"], e["original_name"]))
    wcsv(os.path.join(args.out, "expected.csv"), cols, expected)
    wcsv(os.path.join(args.out, "excluded.csv"),
         ["sha256", "instrument", "size", "reason", "detail", "copies", "path"], excluded)
    wcsv(os.path.join(args.out, "conflicts.csv"), ["sha256", "instrument", "projects", "canonical", "copies"],
         conflicts)
    wcsv(os.path.join(args.out, "batches.csv"),
         ["batch", "bucket", "instrument", "files", "gb", "projects", "members", "auto_create",
          "needs_decision"], batches)

    # ---- summary ------------------------------------------------------------------------------------------
    s = {"generated": dt.datetime.now().isoformat(timespec="seconds"),
         "registry_rows": reg_rows, "production_hashes_mtime": ph_mtime.isoformat(timespec="seconds"),
         "czi_tally": {"|".join(k): v for k, v in sorted(tally.items(), key=str)},
         "copies_in_scope_classes": len(copies), "distinct_contents": len(groups),
         "dup_groups_mismatch": len(dup_mismatch), "canonical_differs_from_strict_rule2": strict_differs,
         "expected": len(expected), "conflicts": len(conflicts), "batches": len(batches)}
    per = collections.defaultdict(lambda: collections.Counter())
    for e in expected:
        k = per[e["instrument"]]
        k["files"] += 1
        k["bytes"] += e["size"]
        k["member"] += e["kind"] == "member"
        k["with_project"] += bool(e["project"])
        k["with_subject"] += bool(e["subject_id"])
        k["blank_project"] += not e["project"]
    s["expected_by_instrument"] = {i: dict(v) for i, v in per.items()}
    ex = collections.defaultdict(lambda: collections.Counter())
    for x in excluded:
        ex[(x["instrument"], x["reason"])]["files"] += 1
        ex[(x["instrument"], x["reason"])]["bytes"] += int(x["size"])
    s["excluded"] = {"|".join(k): dict(v) for k, v in ex.items()}
    s["tif_lsm"] = {"|".join(k): {"files": v[0], "gb": gb(v[1]), "distinct": len(v[2])}
                    for k, v in out_classes.items()}
    s["verdicts"] = dict(collections.Counter(e["verdict"] for e in expected))
    s["projects"] = dict(collections.Counter(f"{e['project']}|{e['project_id']}|{e['project_status']}"
                                             for e in expected if e["project"]))
    with open(os.path.join(args.out, "plan_summary.json"), "w", encoding="utf-8") as f:
        json.dump(s, f, indent=1, ensure_ascii=False)
    print(json.dumps(s, indent=1, ensure_ascii=False))
    for b in batches:
        print(b)


# ---------------------------------------------------------------------------------------------
# plan: drive 3
# ---------------------------------------------------------------------------------------------

D3_PLAN_COLS = ["batch", "sha256", "size", "instrument", "kind", "drive", "relpath", "archive", "member",
                "original_name", "acquisition_datetime", "czi_stand", "instrument_model", "project",
                "project_id", "project_status", "verdict", "claimed", "researcher", "operator", "subject_id",
                "subject_alias", "subject_animal", "sample_id", "sample_type", "data_source", "link_name",
                "notes", "conflict", "n_copies", "other_copies", "acq_group", "acq_group_n", "resave_group_n",
                "top", "same_acq_group", "same_acq_action", "same_acq_note", "farm_path_len"]
OUT_OF_SCOPE_COLS = ["sha256", "relpath", "size", "ext", "instrument", "serials", "stand", "czi_class",
                     "acq_dt", "reason", "in_production"]


def out_of_scope_reason(r):
    """Why an A1 microscopy row is not this stream's (the handoff's out-of-scope list)."""
    if r["ext"].lower() in (".lif", ".lifext"):
        return "Leica TCS SP8 #8100000207: not gjesus3's; waits on M. Jesus, then the Charite XMIC precedent"
    if "4661000340" in (r["serials"] or ""):
        return "Axioscan 7 #4661000340: not gjesus3's ZWSI; waits on M. Jesus, then the Charite XMIC precedent"
    if r["czi_class"] != "czi-raw":
        return f"{r['czi_class']}: no instrument metadata (no hardware/experiment block); not an acquisition record"
    return f"instrument {r['instrument'] or '?'} is not in this stream"


_REF = None


def a1_instrument(r):
    """The instrument of one A1 header row. A1 fingerprinted every .czi against the reference as it stood on
    2026-10-06; a profile with `refingerprint` applies the CURRENT reference (tools/reference/
    microscopy_instruments.yaml, the catalog's rule) to A1's own serials / stand keys / stand, so an entry
    added since (Biodonostia's Axioscan, 2026-10-08) names its rows. A row A1 had already named must come out
    the same, or the reference changed under it: stop."""
    if not PROFILE.get("refingerprint"):
        return r["instrument"]
    global _REF
    import catalog
    if _REF is None:
        _REF = catalog.load_instruments()
    split = lambda v: [x for x in (v or "").split(";") if x]  # noqa: E731
    inst = catalog.fingerprint(_REF, split(r["serials"]), split(r["stand_keys"]), r["stand"])[0]
    if r["instrument"] != "unknown" and inst != r["instrument"]:
        raise SystemExit(f"the reference re-names an instrument A1 had named ({r['instrument']} -> {inst}): "
                         f"{r['relpath']}")
    return inst


def load_copies_drive3():
    """Every copy of a drive-3 .czi in scope, with its claim. Checks A1's sha256/size against the
    drive manifest (A1 is a derived table; the manifest is the staging record)."""
    man = load_manifest(MANIFEST)
    a1 = list(rcsv(A1_FILES))
    for r in a1:
        if r["ext"].lower() == ".czi":
            r["instrument"] = a1_instrument(r)
    want = {r["relpath"] for r in a1}
    fclaims = {}
    for r in rcsv(os.path.join(CODES, "file_claims.csv")):
        if r["drive"] == "drive3" and r["relpath"] in want:
            fclaims[r["relpath"]] = r
    claim_token = {r["claim_id"]: r["token"] for r in rcsv(os.path.join(CODES, "claims.csv"))}
    copies, out_scope, problems = [], [], []
    tally = collections.Counter()
    for r in a1:
        m = man.get(r["relpath"])
        if m is None or m["sha256"] != r["sha256"] or int(m["size"]) != int(r["size"]):
            problems.append(f"A1 row disagrees with the drive manifest: {r['relpath']}")
            continue
        ext = r["ext"].lower()
        tally[(ext, r["czi_class"], r["instrument"])] += 1
        if ext != ".czi" or r["czi_class"] != "czi-raw" or r["instrument"] not in INSTRUMENTS:
            out_scope.append(dict(r, reason=out_of_scope_reason(r), in_production=r["in_prod_raw"]))
            continue
        cl = fclaims.get(r["relpath"])
        if cl is None:
            problems.append(f"no claims row: {r['relpath']}")
            continue
        copies.append({
            "kind": "loose", "drive": "D3", "relpath": r["relpath"], "archive": "", "member": "",
            "path": r["relpath"], "parts": r["relpath"].split("\\"), "sha256": r["sha256"],
            "size": int(r["size"]), "instrument": INSTRUMENTS[r["instrument"]], "acq_dt": r["acq_dt"],
            "stand": r["stand"], "claim": cl,
        })
    if problems:
        raise SystemExit("drive-3 inputs disagree:\n  " + "\n  ".join(problems[:20]))
    return copies, claim_token, out_scope, tally


def contents_to_expected(copies, claim_token, prod, excluded, conflicts):
    """Per-copy fields, one row per distinct content (canonical copy), the hidden-dotfile and
    in-production exclusions. Same rules as the drives 1+2 plan."""
    for c in copies:
        cl = c["claim"]
        verdict = cl["verdict"] or "NO-CLAIM"
        c["verdict"] = verdict
        c["project"] = cl["proposed_project"] if verdict in ("CONFIRMED", "A") else ""
        c["subject_id"] = cl["subject_id"] if verdict == "CONFIRMED" else ""
        c["researcher"], c["operator"] = person_fields(c["drive"], c["parts"], cl["researcher"])
        c["in_backup"] = in_deprioritised(c["path"])
        c["claimed"] = claim_token.get(cl["claim_id"], "")
        c["conflict"] = cl["conflict"]
    groups = collections.defaultdict(list)
    for c in copies:
        groups[c["sha256"]].append(c)
    expected = []
    for sha, cs in groups.items():
        insts = {c["instrument"] for c in cs}
        if len(insts) != 1:
            raise SystemExit(f"one content, two instruments: {sha} {insts}")
        inst = insts.pop()
        size = cs[0]["size"]
        visible = [c for c in cs if not c["path"].split("\\")[-1].startswith(".")]
        if not visible:
            excluded.append({"sha256": sha, "instrument": inst, "size": size, "reason": "hidden-dotfile",
                             "detail": "name starts with '.': the engine's glob cannot see it; list for a one-off",
                             "copies": len(cs), "path": cs[0]["path"]})
            continue
        cs = sorted(visible, key=canon_key)
        if sha in prod:
            excluded.append({"sha256": sha, "instrument": inst, "size": size, "reason": "in-production",
                             "detail": prod[sha], "copies": len(cs), "path": cs[0]["path"]})
            continue
        canon = cs[0]
        projects = sorted({c["project"] for c in cs if c["project"]})
        project, subject, verdict = canon["project"], canon["subject_id"], canon["verdict"]
        conflict_note = ""
        if len(projects) > 1:
            conflicts.append({"sha256": sha, "instrument": inst, "projects": ";".join(projects),
                              "canonical": canon["path"],
                              "copies": " | ".join(f"{c['drive']}:{c['path']} [{c['project'] or '-'}]" for c in cs)})
            project, subject, verdict = "", "", "CONFLICT"
            conflict_note = "copies claim " + " vs ".join(projects)
        subjects = {c["subject_id"] for c in cs if c["project"] == project and c["subject_id"]}
        if project and len(subjects) > 1:
            conflicts.append({"sha256": sha, "instrument": inst, "projects": project, "canonical": canon["path"],
                              "copies": "subject ids disagree: " + ";".join(sorted(subjects))})
            subject = ""
            conflict_note = "copies name different subjects " + ";".join(sorted(subjects))
        label = DRIVES[canon["drive"]][1]
        claim_txt = verdict if verdict != "C" else f"C (path claimed {canon['claimed'] or '?'}; left blank)"
        if verdict == "CONFLICT":
            claim_txt = f"conflict ({conflict_note}); left blank"
        alias = animal = ""
        if subject:
            m = re.fullmatch(r"(\d+)-AE-biomaGUNE-(\d{4})", subject)
            if not m:
                raise SystemExit(f"unexpected subject id {subject!r}")
            animal, alias = m.group(1), m.group(2)
        expected.append({
            "sha256": sha, "size": size, "instrument": inst, "kind": canon["kind"], "drive": canon["drive"],
            "relpath": canon["relpath"], "archive": "", "member": "",
            "original_name": label + "/" + canon["path"].replace("\\", "/"),
            "acquisition_datetime": canon["acq_dt"], "czi_stand": canon["stand"],
            "project": project, "verdict": verdict, "claimed": canon["claimed"] if verdict == "C" else "",
            "researcher": canon["researcher"], "operator": canon["operator"], "subject_id": subject,
            "subject_alias": alias, "subject_animal": animal,
            "sample_id": canon["path"].split("\\")[-1], "sample_type": "tissue" if subject else "",
            "data_source": XMIC_SOURCE if inst == "XMIC" else "internal",
            "instrument_model": XMIC_MODEL if inst == "XMIC" else canon["stand"],
            "notes": NOTE.format(label=label, claim=claim_txt),
            "conflict": conflict_note or canon["conflict"],
            "n_copies": len(cs),
            "other_copies": ";".join(f"{DRIVES[c['drive']][1]}/{c['path'].replace(chr(92), '/')}" for c in cs[1:]),
            "top": canon["parts"][0], "_c": canon, "_copies": cs,
        })
    return expected, groups


def farm_path_len(e):
    """Length of the farm path the engine will open (no \\?\\ prefix: must stay under MAX_PATH)."""
    return len(os.path.join(FARM, "C00", e["original_name"].replace("/", "\\")))


def cut_even(rows, cap):
    """Cut rows (in their order) into chunks of at most `cap` bytes (a hard limit; one row bigger than the
    cap is a chunk of its own), aiming at the fewest chunks of roughly equal size (a soft target)."""
    total = sum(int(r["size"]) for r in rows)
    n = max(1, -(-total // cap))
    target = total / n
    chunks, cur, size = [], [], 0
    for r in rows:
        s = int(r["size"])
        # close before this row when it would pass the cap, or when that lands nearer the target
        nearer = size + s > target and (target - size) < (size + s - target)
        if cur and (size + s > cap or (len(chunks) < n - 1 and nearer)):
            chunks.append(cur)
            cur, size = [], 0
        cur.append(r)
        size += s
        if len(chunks) < n - 1 and size >= target:
            chunks.append(cur)
            cur, size = [], 0
    if cur:
        chunks.append(cur)
    return chunks


def pilot_selection(expected):
    """The first batch: a few small files of every kind the ingest handles, so that the rehearsal and the
    first production window exercise every code path cheaply -- each project's smallest files with and
    without a subject link, the smallest files with no project, the smallest flagged same-acquisition
    members, and the deepest farm paths. Deterministic (size, then name). biomaGUNE MJ stays apart."""
    rows = [e for e in expected if e["top"] not in DEPRIORITISED_TOPS]
    small = lambda es: sorted(es, key=lambda e: (int(e["size"]), e["original_name"]))  # noqa: E731
    pick = []
    for p in sorted({e["project"] for e in rows if e["project"]}):
        pe = [e for e in rows if e["project"] == p]
        pick += small([e for e in pe if e["subject_id"]])[:PILOT["per_project"]]
        pick += small([e for e in pe if not e["subject_id"]])[:PILOT["per_project_no_subject"]]
    pick += small([e for e in rows if not e["project"]])[:PILOT["no_project"]]
    groups = collections.defaultdict(list)            # whole groups, so a group is exercised end to end
    for e in rows:
        if e.get("acq_group"):
            groups[e["acq_group"]].append(e)
    taken = 0
    for g in sorted(groups, key=lambda g: (sum(int(e["size"]) for e in groups[g]), g)):
        if taken >= PILOT["flagged"]:
            break
        pick += groups[g]
        taken += len(groups[g])
    pick += sorted(rows, key=lambda e: (-e["farm_path_len"], int(e["size"]), e["original_name"]))[:PILOT["deepest"]]
    return {e["sha256"] for e in pick}


def production_primary(nas, r):
    return os.path.join(nas, r["canonical_path"].strip("/").replace("/", "\\"), r["primary_file_name"])


# Readings (the A2 R1-R4 kind): evidence-based fills of a blank project, each listed for the coordinator and
# applied ONLY when its row in <config dir>\readings.csv says `accepted`. A reading fills a (C) or no-claim
# file's project; it never overrules a Confirmed claim. Kind `both-protocols-near`: the engine left the
# file (C) because "nearest <near> (CONFIRMED) vs outer <outer>; animal N is found in BOTH" -- the reading
# takes the nearer claim, and the subject is animal N of that protocol (re-resolved in the DB by check 6).
READING_COLS = ["reading", "status", "kind", "prefix", "project", "summary", "evidence", "decided"]
BOTH_RX = re.compile(r"nearest (\d{4}) \(CONFIRMED\) vs outer (\d{4}); animal (\d+) is found in BOTH")


def load_readings(config_dir=None):
    p = os.path.join(config_dir or CONFIG_DIR, "readings.csv")
    return list(rcsv(p)) if os.path.isfile(p) else []


# Label readings (the XMIC profile, 2026-10-08): a whole-slide scanner photographs the slide's paper label and stores
# the photo inside the .czi (attachment `Label`), so the file itself says what the slide is. <config dir>\
# label_readings.csv holds, per distinct content, the label as read (by a person, from the contact sheets), the
# protocol and animal it names, and the reading that would use it. Kind `label` fills a (C) / no-claim row; kind
# `label-overrule` replaces a CONFIRMED folder claim the file's own label contradicts. Both apply ONLY when their
# row in readings.csv says `accepted`, and only where the label names a protocol and an animal.
LABEL_COLS = ["n", "sha256", "relpath", "label", "protocol", "animal", "reading", "note"]


def load_labels(config_dir=None):
    p = os.path.join(config_dir or CONFIG_DIR, "label_readings.csv")
    return {r["sha256"]: r for r in rcsv(p)} if os.path.isfile(p) else {}


def apply_label_readings(expected, readings, labels):
    """The label kinds of apply_readings (pure: tested). Returns (applied, would) Counters."""
    applied, would = collections.Counter(), collections.Counter()
    kinds = {r["reading"]: r for r in readings if r["kind"] in ("label", "label-overrule")}
    if not kinds or not labels:
        return applied, would
    for e in expected:
        lab = labels.get(e.get("sha256"))
        if not lab or lab["reading"] not in kinds or not (lab["protocol"] and lab["animal"]):
            continue
        r = kinds[lab["reading"]]
        code, animal = lab["protocol"], str(int(lab["animal"]))
        project = f"AE-biomaGUNE-{code}"
        if r["kind"] == "label" and e["verdict"] not in ("C", "NO-CLAIM"):
            continue
        if r["kind"] == "label-overrule" and not (e["verdict"] == "CONFIRMED" and e["project"] != project):
            continue
        if r["status"] != "accepted":
            would[r["reading"]] += 1
            continue
        was = e["verdict"] if e["verdict"] != "CONFIRMED" else f"CONFIRMED {e['project']}"
        e.update(project=project, verdict=f"READING-{r['reading']}", subject_id=f"{animal}-AE-biomaGUNE-{code}",
                 subject_alias=code, subject_animal=animal, sample_type="tissue")
        e["notes"] = NOTE.format(label=DRIVES[e["drive"]][1],
                                 claim=f"{was}, {'filled' if r['kind'] == 'label' else 'replaced'} by reading "
                                       f"{r['reading']} (accepted {r['decided']}): the slide label in the file reads "
                                       f"'{lab['label']}'")
        applied[r["reading"]] += 1
    return applied, would


def apply_readings(expected, readings, labels=None):
    """Fill the project (and the subject) of the (C) / no-claim rows an ACCEPTED reading covers. Returns
    {reading: rows applied} and, for the proposed (not accepted) ones, {reading: rows it would fill}. The label
    kinds (above) read `labels` ({sha256: label_readings row}); the folder kinds read the reading's prefix."""
    applied, would = apply_label_readings(expected, readings, labels or {})
    readings = [r for r in readings if r["kind"] not in ("label", "label-overrule")]
    for e in expected:
        if e["verdict"] not in ("C", "NO-CLAIM"):
            continue
        for r in readings:
            if not e["relpath"].startswith(r["prefix"].rstrip("\\") + "\\"):
                continue
            code = r["project"][-4:]
            animal = ""
            if r["kind"] == "both-protocols-near":
                m = BOTH_RX.search(e.get("conflict", ""))
                if not m or m.group(1) != code:
                    continue
                animal = m.group(3)
            elif r["kind"] != "folder":
                raise SystemExit(f"readings.csv: unknown kind {r['kind']!r}")
            if r["status"] != "accepted":
                would[r["reading"]] += 1
                break
            e.update(project=r["project"], verdict=f"READING-{r['reading']}")
            if animal:
                e.update(subject_id=f"{animal}-AE-biomaGUNE-{code}", subject_alias=code, subject_animal=animal,
                         sample_type="tissue")
            e["notes"] = NOTE.format(label=DRIVES[e["drive"]][1],
                                     claim=f"C, filled by reading {r['reading']} (accepted {r['decided']}): "
                                           f"{r['summary']}")
            applied[r["reading"]] += 1
            break
    return applied, would


def apply_people(expected):
    """Fill a blank researcher / operator from PEOPLE_BY_FOLDER, by the canonical copy's path, then from the
    profile's `people_all` (a ruling for every file). Returns {(field, value): rows filled}."""
    filled = collections.Counter()
    for e in expected:
        rel = e["relpath"].lower()
        for prefix, field, value in PEOPLE_BY_FOLDER:
            if rel.startswith(prefix.lower()) and not e[field]:
                e[field] = value
                filled[(field, value)] += 1
        for field, value in PROFILE.get("people_all", ()):     # a ruling for every file of the profile
            if not e[field]:
                e[field] = value
                filled[(field, value)] += 1
    return filled


def plan_drive3(args):
    """The drive-3 plan (two passes: the first lists the same-acquisition groups for the pixel check,
    drive3/c_groups.py; the second applies its decisions -- or reports them undecided)."""
    os.makedirs(args.out, exist_ok=True)
    print("production hashes ...", file=sys.stderr)
    ph_path = os.path.join(CAT, "production_hashes.csv")
    prod, prod_sha_of = {}, collections.defaultdict(list)
    for r in rcsv(ph_path):
        prod.setdefault(r["sha256"], r["acq_id"])
        prod_sha_of[r["acq_id"]].append(r["sha256"])
    reg_path = os.path.join(args.nas, "registries", "registry_raw.csv")
    reg = list(rcsv(reg_path))
    if os.path.getmtime(reg_path) > os.path.getmtime(ph_path):
        print(f"WARN: registry_raw.csv is newer than {ph_path}: re-run catalog.py production --out {CAT}",
              file=sys.stderr)
    print("drive-3 copies + claims ...", file=sys.stderr)
    copies, claim_token, out_scope, tally = load_copies_drive3()
    excluded, conflicts = [], []
    expected, contents = contents_to_expected(copies, claim_token, prod, excluded, conflicts)
    n_candidates = len(expected)
    cdir = getattr(args, "config_dir", None) or CONFIG_DIR     # --config-dir: a variant's readings (the gate's L1/L2)
    readings_applied, readings_proposed = apply_readings(expected, load_readings(cdir), load_labels(cdir))
    people_filled = apply_people(expected)
    print(f"people by folder: {dict(people_filled)}", file=sys.stderr)

    # ---- R1: a re-save of a production acquisition (same instrument, second and name) -------------
    by_key, by_ts = production_index(args.nas)
    kept, r1_review = [], []
    for e in expected:
        names = {_base(c["path"]) for c in e["_copies"]}
        twins = []
        for n in sorted(names):
            twins += by_key.get((e["instrument"], e["acquisition_datetime"][:19], n), [])
        twins = list({t["acq_id"]: t for t in twins}.values())
        if not twins:
            kept.append(e)
            continue
        if len(twins) > 1:
            raise SystemExit(f"R1: {e['original_name']} matches {len(twins)} production rows")
        t = twins[0]
        diff = int(e["size"]) - os.path.getsize(production_primary(args.nas, t))
        e["_r1"] = (t, diff)
        if abs(diff) <= RESAVE_SIZE_TOL:
            excluded.append({"sha256": e["sha256"], "instrument": e["instrument"], "size": e["size"],
                             "reason": "resave-of-production",
                             "detail": f"resave-of-production:{t['acq_id']}; size diff {diff} B",
                             "copies": e["n_copies"], "path": e["original_name"]})
            continue
        r1_review.append(e["sha256"])     # decided by the pixel check, with its production twin
        kept.append(e)
    expected = kept

    # ---- same-acquisition groups: planned files + production rows of one instrument and second -------
    by_group = collections.defaultdict(list)
    for e in expected:
        by_group[group_id(e["instrument"], e["acquisition_datetime"])].append(e)
    decisions = collections.defaultdict(dict)
    dpath = os.path.join(args.out, "pixel_decisions.csv")
    if os.path.isfile(dpath):
        for d in rcsv(dpath):
            decisions[d["group"]][d["member"]] = d
    cand_rows, nonraw, repairs = [], [], []
    kept = []
    group_stats = collections.Counter()
    proj_name_of = {r["project_id"]: r["name"]
                    for r in rcsv(os.path.join(args.nas, "registries", "registry_projects.csv"))}
    for gid, es in sorted(by_group.items()):
        inst, ts = gid.split("|", 1)
        prows = by_ts.get((inst, ts), [])
        if len(es) + len(prows) < 2:
            e = es[0]
            e.update(same_acq_group="", same_acq_action="", same_acq_note="")
            kept.append(e)
            continue
        group_stats["groups"] += 1
        group_stats["with_production"] += bool(prows)
        for e in es:
            cand_rows.append({"group": gid, "member": e["sha256"], "role": "plan", "sha256": e["sha256"],
                              "acq_id": "", "path": local_path(e["relpath"]), "size": e["size"],
                              "name": e["original_name"].split("/")[-1], "project": e["project"],
                              "original_name": e["original_name"]})
        for p in prows:
            shas = prod_sha_of.get(p["acq_id"], [])
            cand_rows.append({"group": gid, "member": p["acq_id"], "role": "production",
                              "sha256": shas[0] if len(shas) == 1 else "", "acq_id": p["acq_id"],
                              "path": production_primary(args.nas, p),
                              "size": os.path.getsize(production_primary(args.nas, p)),
                              "name": p["original_name"].split("/")[-1],
                              "project": p["project_id"], "original_name": p["original_name"]})
        acts = same_acquisition_actions(es, prows, decisions.get(gid, {}))
        dec = decisions.get(gid, {})
        by_sha = {e["sha256"]: e for e in es}
        by_acq = {p["acq_id"]: p for p in prows}
        n_keep = sum(1 for e in es if acts[e["sha256"]][0] in (ACTION_KEEP, ACTION_FLAG, ACTION_UNDECIDED))
        for e in es:
            group_stats["action:" + acts[e["sha256"]][0]] += 1
            e.update(same_acq_group=gid, same_acq_action=acts[e["sha256"]][0], same_acq_note=acts[e["sha256"]][2])
        # pass 1: a same-name twin of the kept file -- a dropped re-save, or a scale-bar copy routed to the
        # project folder -- is the same acquisition: a single claimed project carries over to the kept file, and
        # a dropped re-save's path joins the kept file's other_copies
        for e in es:
            action, parent, note = acts[e["sha256"]]
            keep = by_sha.get(parent)
            twin = keep is not None and _base(keep["original_name"]) == _base(e["original_name"])
            if action == ACTION_DROP:
                excluded.append({"sha256": e["sha256"], "instrument": e["instrument"], "size": e["size"],
                                 "reason": "resave-of-production" if parent in by_acq else "resave-within-plan",
                                 "detail": f"{note}; kept {parent}", "copies": e["n_copies"],
                                 "path": e["original_name"]})
                if keep is not None:
                    keep["other_copies"] = ";".join(x for x in [keep["other_copies"], e["original_name"],
                                                                 e["other_copies"]] if x)
                    keep["n_copies"] = int(keep["n_copies"]) + int(e["n_copies"])
                    keep["resave_group_n"] = str(int(keep.get("resave_group_n") or 1) + 1)
            elif action != ACTION_NONRAW:
                continue
            if not twin:
                continue
            what = "re-save" if action == ACTION_DROP else "scale-bar copy"
            if not keep["project"] and e["project"] and keep["verdict"] != "CONFLICT":
                for k in ("project", "verdict", "subject_id", "subject_alias", "subject_animal", "sample_type"):
                    keep[k] = e[k]
                keep["notes"] = NOTE.format(label=DRIVES[keep["drive"]][1], claim=keep["verdict"])
                keep["notes"] = (keep["notes"].rstrip(".") + f"; project from its pixel-identical {what} "
                                 f"{e['original_name']}.")
            elif keep["project"] and e["project"] and keep["project"] != e["project"]:
                both = f"{keep['project']} and {e['project']}"
                conflicts.append({"sha256": keep["sha256"], "instrument": keep["instrument"],
                                  "projects": f"{keep['project']};{e['project']}", "canonical": keep["original_name"],
                                  "copies": f"same-name pixel-identical {what} claims another project: "
                                            + e["original_name"]})
                keep.update(project="", subject_id="", subject_alias="", subject_animal="", verdict="CONFLICT",
                            sample_type="")
                keep["notes"] = NOTE.format(label=DRIVES[keep["drive"]][1],
                                            claim=f"conflict (its pixel-identical twins claim {both}); left blank")
        # pass 2: the kept files (notes), the derivatives (non-raw, to the kept original's FINAL project), holds
        for e in es:
            action, parent, note = acts[e["sha256"]]
            if action == ACTION_DROP:
                continue
            if action in (ACTION_KEEP, ACTION_FLAG, ACTION_UNDECIDED):
                if n_keep > 1 or prows or action != ACTION_KEEP:
                    e["acq_group"] = gid
                    e["acq_group_n"] = str(n_keep)
                    clause = {ACTION_KEEP: "the pixel check found no copy relation (another scene of the acquisition)",
                              ACTION_FLAG: note,
                              ACTION_UNDECIDED: "NOT YET DECIDED by the pixel check"}[action]
                    if prows:
                        clause += f"; same second as production {';'.join(p['acq_id'] for p in prows)}"
                    e["notes"] = (e["notes"].rstrip(".") + f"; shares its acquisition second with "
                                  f"{n_keep - 1 + len(prows)} other file(s): {clause}.")
                derived = [x for x in es if acts[x["sha256"]][0] == ACTION_NONRAW
                           and acts[x["sha256"]][1] == e["sha256"]]
                if derived:
                    e["notes"] = (e["notes"].rstrip(".") + f"; {len(derived)} derivative file(s) of it (same "
                                  "acquisition second) are kept as non-raw material in the project folder.")
                kept.append(e)
                continue
            par = dec.get(parent, {})
            par_plan, par_prod = by_sha.get(parent), by_acq.get(parent)
            if action == ACTION_HOLD:
                excluded.append({"sha256": e["sha256"], "instrument": e["instrument"], "size": e["size"],
                                 "reason": "held-production-repair", "detail": f"{note}; group {gid}",
                                 "copies": e["n_copies"], "path": e["original_name"]})
                kind = ("incomplete-in-production" if par.get("complete") == "N" else
                        "same-name-other-pixels" if par.get("class") in ROOT_CLASSES else
                        "derivative-in-production")
                repairs.append({"kind": kind, "acq_id": parent,
                                "production_original_name": par_prod["original_name"] if par_prod else "",
                                "production_size": par.get("size", ""), "production_class": par.get("class", ""),
                                "production_complete": par.get("complete", ""),
                                "drive_sha256": e["sha256"], "drive_size": e["size"],
                                "drive_original_name": e["original_name"], "drive_relpath": e["relpath"],
                                "evidence": par.get("evidence", ""), "note": note})
                continue
            if action == ACTION_NONRAW:
                pproj = (par_plan["project"] if par_plan else
                         proj_name_of.get(par_prod["project_id"], par_prod["project_id"]) if par_prod else "")
                dnote = "the original's project" if pproj else "the original has no project: the holding folder"
                if e["project"] and pproj and e["project"] != pproj:
                    dnote = f"CONFLICT: its own claim {e['project']} differs from the original's {pproj}"
                nonraw.append({"sha256": e["sha256"], "instrument": e["instrument"], "size": e["size"],
                               "original_name": e["original_name"], "drive": e["drive"], "relpath": e["relpath"],
                               "class": (dec.get(e["sha256"]) or {}).get("class", ""), "why": note,
                               "evidence": (dec.get(e["sha256"]) or {}).get("evidence", ""),
                               "parent_sha256": parent if par_plan else "",
                               "parent_acq_id": parent if par_prod else "",
                               "parent_original_name": (par_plan or par_prod or {}).get("original_name", ""),
                               "parent_project": pproj, "own_claim_project": e["project"],
                               "destination_project": pproj, "destination_note": dnote,
                               "acquisition_datetime": e["acquisition_datetime"]})
                excluded.append({"sha256": e["sha256"], "instrument": e["instrument"], "size": e["size"],
                                 "reason": "derivative-nonraw", "detail": f"{note}; -> nonraw_derived.csv",
                                 "copies": e["n_copies"], "path": e["original_name"]})
                continue
            raise SystemExit(f"unhandled same-acquisition action {action!r} for {e['original_name']}")
    expected = kept
    wcsv(os.path.join(args.out, "pixel_candidates.csv"), PIXEL_CAND_COLS, cand_rows)
    wcsv(os.path.join(args.out, "nonraw_derived.csv"), NONRAW_D3_COLS, nonraw)
    wcsv(os.path.join(args.out, "production_repairs.csv"), REPAIR_COLS, repairs)

    # ---- projects: every target exists and is active (this ingest creates and reopens nothing) ------
    projects = load_projects(args.nas)
    for e in expected:
        p = projects.get(e["project"].lower()) if e["project"] else None
        e["project_id"] = p["project_id"] if p else ""
        e["project_status"] = p["status"] if p else ""
        if e["project"] and not p:
            raise SystemExit(f"project {e['project']} is not in production (this ingest creates none)")
        if e["project"] and p["status"] != "active":
            raise SystemExit(f"project {e['project']} is {p['status']} (this ingest reopens none)")

    # ---- batches: a pilot first; then projects, then no project; biomaGUNE MJ last and apart --------
    for e in expected:
        e["farm_path_len"] = farm_path_len(e)
        if e["farm_path_len"] > MAX_FARM_PATH:
            raise SystemExit(f"farm path {e['farm_path_len']} > {MAX_FARM_PATH} characters: {e['original_name']}")
    pilot = pilot_selection(expected)

    def bucket(e):       # stream C: CELL-pilot, CELL-project, ...; the XMIC profile: XMIC-pilot, ...
        if e["top"] in DEPRIORITISED_TOPS:
            return f"{e['instrument']}-biomaGUNE-MJ"
        if e["sha256"] in pilot:
            return f"{e['instrument']}-pilot"
        return f"{e['instrument']}-project" if e["project"] else f"{e['instrument']}-noproject"

    by_bucket = collections.defaultdict(list)
    for e in expected:
        by_bucket[bucket(e)].append(e)
    order = {"pilot": 0, "project": 1, "noproject": 2, "biomaGUNE-MJ": 3}
    chunks = []
    for b in sorted(by_bucket, key=lambda b: (order[b.split("-", 1)[1]], b)):
        es = sorted(by_bucket[b], key=lambda e: (e["project"], e["original_name"]))
        chunks += [(b, c) for c in cut_even(es, BATCH_CAP)]
    batches = []
    for n, (b, es) in enumerate(chunks, 1):
        bid = f"{BATCH_PREFIX}{n:02d}"
        for e in es:
            e["batch"] = bid
        size = sum(e["size"] for e in es)
        if size > BATCH_CAP:
            raise SystemExit(f"batch {bid} is {gb(size)} GB, over the cap")
        batches.append({"batch": bid, "bucket": b, "instrument": es[0]["instrument"], "files": len(es),
                        "gb": gb(size), "projects": ";".join(sorted({e["project"] for e in es if e["project"]}))
                        or "(none)", "members": 0, "auto_create": "N", "needs_decision": ""})

    assign_link_names(expected, projects, args.nas)

    expected.sort(key=lambda e: (e["batch"], e["original_name"]))
    wcsv(os.path.join(args.out, "expected.csv"), D3_PLAN_COLS, expected)
    wcsv(os.path.join(args.out, "excluded.csv"),
         ["sha256", "instrument", "size", "reason", "detail", "copies", "path"], excluded)
    wcsv(os.path.join(args.out, "conflicts.csv"), ["sha256", "instrument", "projects", "canonical", "copies"],
         conflicts)
    wcsv(os.path.join(args.out, "out_of_scope.csv"), OUT_OF_SCOPE_COLS,
         [{**r, "relpath": r["relpath"]} for r in out_scope])
    wcsv(os.path.join(args.out, "batches.csv"),
         ["batch", "bucket", "instrument", "files", "gb", "projects", "members", "auto_create",
          "needs_decision"], batches)

    undecided = sum(1 for e in expected if e.get("same_acq_action") == ACTION_UNDECIDED)
    s = {"generated": dt.datetime.now().isoformat(timespec="seconds"), "profile": PROFILE_NAME,
         "registry_rows": len(reg),
         "production_hashes_mtime": dt.datetime.fromtimestamp(os.path.getmtime(ph_path)).isoformat(timespec="seconds"),
         "a1_tally": {"|".join(k): v for k, v in sorted(tally.items(), key=str)},
         "copies_in_scope": len(copies), "distinct_contents": len(contents),
         "candidates_not_in_production": n_candidates,
         "readings_applied": dict(readings_applied), "readings_proposed_not_applied": dict(readings_proposed),
         "r1_size_review": len(r1_review), "same_acquisition_groups": dict(group_stats),
         "pixel_candidates": len(cand_rows), "undecided_rows": undecided,
         "expected": len(expected), "expected_gb": gb(sum(e["size"] for e in expected)),
         "nonraw": len(nonraw), "production_repairs": len(repairs), "conflicts": len(conflicts),
         "batches": len(batches),
         "out_of_scope": dict(collections.Counter(r["reason"].split(":")[0] for r in out_scope))}
    ex = collections.defaultdict(lambda: collections.Counter())
    for x in excluded:
        ex[x["reason"]]["files"] += 1
        ex[x["reason"]]["bytes"] += int(x["size"])
    s["excluded"] = {k: dict(v) for k, v in ex.items()}
    s["verdicts"] = dict(collections.Counter(e["verdict"] for e in expected))
    s["projects"] = dict(collections.Counter(f"{e['project']}|{e['project_id']}" for e in expected if e["project"]))
    s["max_farm_path"] = max((e["farm_path_len"] for e in expected), default=0)
    labels = load_labels(cdir)
    if labels:     # the XMIC profile: every planned row's project and subject against its slide's own label
        lab_rows = []
        for e in expected:
            lab = labels.get(e["sha256"])
            if lab is None:
                continue
            want = ((f"AE-biomaGUNE-{lab['protocol']}", f"{int(lab['animal'])}-AE-biomaGUNE-{lab['protocol']}")
                    if lab["protocol"] and lab["animal"] else None)
            got = (e["project"], e["subject_id"])
            agree = ("label names no protocol" if want is None else "agree" if got == want else
                     "blank, label names one" if not e["project"] else "DISAGREE")
            lab_rows.append({"original_name": e["original_name"], "batch": e["batch"], "verdict": e["verdict"],
                             "project": e["project"], "subject_id": e["subject_id"], "label": lab["label"],
                             "label_project": want[0] if want else "", "label_subject": want[1] if want else "",
                             "result": agree})
        wcsv(os.path.join(args.out, "label_check.csv"), list(lab_rows[0]) if lab_rows else ["original_name"],
             lab_rows)
        s["label_check"] = dict(collections.Counter(r["result"] for r in lab_rows))
    with open(os.path.join(args.out, "plan_summary.json"), "w", encoding="utf-8") as f:
        json.dump(s, f, indent=1, ensure_ascii=False)
    print(json.dumps(s, indent=1, ensure_ascii=False))
    for b in batches:
        print(b)
    if undecided:
        print(f"NOTE: {undecided} planned rows sit in same-acquisition groups the pixel check has not decided: "
              f"run drive3/c_groups.py, then plan again", file=sys.stderr)


# ---------------------------------------------------------------------------------------------
# extract: archive-only canonical copies (drives 1+2)
# ---------------------------------------------------------------------------------------------

def load_expected(out):
    return list(rcsv(os.path.join(out, "expected.csv")))


def cmd_extract(args):
    """7-Zip each needed member (and only those) out of its archive, one archive at a time, then
    verify every extracted file against the catalog's sha256. Idempotent: a member already
    extracted with the right hash is left alone. Never LEONE.zip or Cardiac MRI.zip."""
    exp = [e for e in load_expected(args.out) if e["kind"] == "member"]
    by_arc = collections.defaultdict(list)
    for e in exp:
        by_arc[(e["drive"], e["archive"])].append(e)
    bad = 0
    for (drive, arc), es in sorted(by_arc.items()):
        name = arc.split("\\")[-1]
        if name.lower() in ("leone.zip", "cardiac mri.zip"):
            raise SystemExit(f"refusing to extract {name}")
        dest = os.path.join(EXTRACT, archive_key(drive, arc))
        todo = [e for e in es if not (os.path.isfile(longpath(os.path.join(dest, e["member"])))
                                      and os.path.getsize(longpath(os.path.join(dest, e["member"]))) == int(e["size"]))]
        print(f"{arc}: {len(es)} members needed, {len(todo)} to extract -> {dest}", flush=True)
        if todo:
            os.makedirs(longpath(dest), exist_ok=True)
            lst = os.path.join(args.out, f"_extract_list_{archive_key(drive, arc)}.txt")
            with open(lst, "w", encoding="utf-8") as f:
                for e in todo:
                    f.write(e["member"] + "\n")
            # -spd: names are literal (no wildcards: `[`/`?` occur); -scsUTF-8: the list file's charset
            cmd = [SEVENZIP, "x", "-y", "-spd", "-scsUTF-8", f"-o{dest}", staged_path(drive, arc), f"@{lst}"]
            rc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
            if rc.returncode != 0:
                print(rc.stdout[-2000:], rc.stderr[-2000:])
                raise SystemExit(f"7-Zip failed on {arc} (rc={rc.returncode})")
        for e in es:
            p = os.path.join(dest, e["member"].replace("/", "\\"))
            got = sha256_file(p) if os.path.isfile(longpath(p)) else "MISSING"
            if got != e["sha256"]:
                bad += 1
                print(f"  HASH MISMATCH {e['member']}: {got[:12]} != {e['sha256'][:12]}")
    print(f"extract: {len(exp)} members, {bad} bad")
    if bad:
        raise SystemExit(1)


# ---------------------------------------------------------------------------------------------
# localize (drive 3): the staged copy is on the NAS share (J:), the farm must be on the volume it
# links into, and the engine reads every source twice (hash, then copy). So each planned file is copied
# ONCE from J: to the local mirror on D:, its SHA-256 computed from the bytes as they are read and
# compared with the drive manifest; a mismatch keeps nothing. Read-only on J:.
# ---------------------------------------------------------------------------------------------

LOCALIZE_LOG_COLS = ["relpath", "size", "sha256", "result", "seconds", "when"]


def copy_verified(src, dst, want_sha, want_size, mtime_ns=None):
    """Copy src -> dst through dst.part, hashing the bytes as they are read; keep it only if the hash and
    size equal the manifest's. Returns (ok, detail). Never opens src for writing."""
    part = dst + ".part"
    os.makedirs(os.path.dirname(longpath(dst)), exist_ok=True)
    h, n = hashlib.sha256(), 0
    with open(longpath(src), "rb") as fi, open(longpath(part), "wb") as fo:
        for b in iter(lambda: fi.read(16 * 1024 * 1024), b""):
            h.update(b)
            n += len(b)
            fo.write(b)
    got = h.hexdigest()
    if got != want_sha or n != int(want_size):
        os.remove(longpath(part))
        return False, f"read {n} B sha256 {got[:16]}, manifest {int(want_size)} B {want_sha[:16]}"
    os.replace(longpath(part), longpath(dst))
    if mtime_ns:
        os.utime(longpath(dst), ns=(int(mtime_ns), int(mtime_ns)))
    return True, "copied"


def cmd_localize(args):
    if not LOCAL:
        raise SystemExit(f"profile {PROFILE_NAME} has no local mirror (its farm links the staged copy)")
    if os.path.normcase(os.path.abspath(LOCAL)).startswith(os.path.normcase(os.path.abspath(STAGING))):
        raise SystemExit("the local mirror may not live under the staged tree")
    keep_awake()
    exp = load_expected(args.out)
    if args.subset == "pixel":
        want = {r["sha256"] for r in rcsv(os.path.join(args.out, "pixel_candidates.csv")) if r["role"] == "plan"}
        exp = [e for e in exp if e["sha256"] in want]
    elif args.batch:
        exp = [e for e in exp if e["batch"] in set(args.batch)]
    man = load_manifest(MANIFEST)
    log_path = os.path.join(args.out, "localize_log.csv")
    done = {}
    if os.path.isfile(log_path):
        for r in rcsv(log_path):
            if r["result"] in ("copied", "present-verified"):
                done[r["relpath"]] = r
    todo, rows = [], []
    for e in exp:
        m = man[e["relpath"]]
        if m["sha256"] != e["sha256"] or int(m["size"]) != int(e["size"]):
            raise SystemExit(f"plan row disagrees with the manifest: {e['relpath']}")
        dst = local_path(e["relpath"])
        have = os.path.isfile(longpath(dst)) and os.path.getsize(longpath(dst)) == int(e["size"])
        if have and e["relpath"] in done and not args.rehash:
            continue
        todo.append((e, m, have))
    total = sum(int(e["size"]) for e, _m, _h in todo)
    print(f"{len(exp)} planned files; {len(todo)} to copy or verify ({gb(total)} GB) -> {LOCAL}", flush=True)
    t0, nbytes, bad = time.time(), 0, []
    lock_rows = []

    def one(item):
        e, m, have = item
        dst = local_path(e["relpath"])
        t = time.time()
        if have:
            got = sha256_file(dst)
            ok = got == e["sha256"]
            res = "present-verified" if ok else "present-MISMATCH"
            if not ok:
                os.remove(longpath(dst))
        else:
            ok, detail = copy_verified(staged_path(e["drive"], e["relpath"]), dst, e["sha256"], e["size"],
                                       m.get("mtime_ns"))
            res = "copied" if ok else "MISMATCH " + detail
        return e, res, time.time() - t

    # big files one at a time (the link is the limit), small ones a few at a time (latency)
    big = [x for x in todo if int(x[0]["size"]) >= 64 * 10**6]
    small = [x for x in todo if int(x[0]["size"]) < 64 * 10**6]
    with cf.ThreadPoolExecutor(2) as exb, cf.ThreadPoolExecutor(4) as exs:
        futs = [exb.submit(one, x) for x in big] + [exs.submit(one, x) for x in small]
        for i, fut in enumerate(cf.as_completed(futs), 1):
            e, res, secs = fut.result()
            nbytes += int(e["size"])
            lock_rows.append({"relpath": e["relpath"], "size": e["size"], "sha256": e["sha256"], "result": res,
                              "seconds": f"{secs:.1f}", "when": dt.datetime.now().isoformat(timespec="seconds")})
            if not res.startswith(("copied", "present-verified")):
                bad.append((e["relpath"], res))
            if i % 100 == 0 or i == len(futs):
                el = time.time() - t0
                print(f"  {i}/{len(futs)} files, {gb(nbytes)} GB, {nbytes / 1e6 / max(el, 1):.0f} MB/s, "
                      f"{len(bad)} bad", flush=True)
                old = [r for r in done.values() if r["relpath"] not in {x["relpath"] for x in lock_rows}]
                wcsv(log_path, LOCALIZE_LOG_COLS, old + lock_rows)
    old = [r for r in done.values() if r["relpath"] not in {x["relpath"] for x in lock_rows}]
    wcsv(log_path, LOCALIZE_LOG_COLS, old + lock_rows)
    el = time.time() - t0
    print(f"localize: {len(todo)} files, {gb(nbytes)} GB in {el:.0f}s ({nbytes / 1e6 / max(el, 1):.0f} MB/s), "
          f"{len(bad)} bad")
    for p, r in bad[:20]:
        print(f"  BAD {p}: {r}")
    if bad:
        raise SystemExit(1)


def cmd_verify_local(args):
    """Re-hash local-mirror files FROM DISK against the drive manifest (not the plan, not the copy log):
    an independent proof that the bytes on D: are the drive's, before they are farmed or ingested. Reads
    the mirror only. `--batch` / `--subset pixel` narrow it; the default is every planned file."""
    if not LOCAL:
        raise SystemExit(f"profile {PROFILE_NAME} has no local mirror")
    keep_awake()
    exp = load_expected(args.out)
    if args.subset == "pixel":
        want = {r["sha256"] for r in rcsv(os.path.join(args.out, "pixel_candidates.csv")) if r["role"] == "plan"}
        exp = [e for e in exp if e["sha256"] in want]
    elif args.batch:
        exp = [e for e in exp if e["batch"] in set(args.batch)]
    man = load_manifest(MANIFEST)
    t0, nbytes, bad = time.time(), 0, []

    def one(e):
        m = man.get(e["relpath"])
        p = local_path(e["relpath"])
        if m is None:
            return e, "not in the drive manifest"
        if not os.path.isfile(longpath(p)):
            return e, "missing from the local mirror"
        if os.path.getsize(longpath(p)) != int(m["size"]):
            return e, f"size {os.path.getsize(longpath(p))} != manifest {m['size']}"
        got = sha256_file(p)
        return e, "" if got == m["sha256"] else f"sha256 {got[:16]} != manifest {m['sha256'][:16]}"

    with cf.ThreadPoolExecutor(args.workers) as ex:
        for i, (e, err) in enumerate(ex.map(one, exp), 1):
            nbytes += int(e["size"])
            if err:
                bad.append((e["relpath"], err))
            if i % 250 == 0 or i == len(exp):
                el = time.time() - t0
                print(f"  {i}/{len(exp)} files, {gb(nbytes)} GB, {nbytes / 1e6 / max(el, 1):.0f} MB/s, {len(bad)} bad",
                      flush=True)
    print(f"verify-local: {len(exp)} files, {gb(nbytes)} GB re-hashed from {LOCAL} against {MANIFEST}: "
          f"{len(exp) - len(bad)} match, {len(bad)} bad")
    for p, r in bad[:20]:
        print(f"  BAD {p}: {r}")
    if bad:
        raise SystemExit(1)


# ---------------------------------------------------------------------------------------------
# farm: one hard-link tree per batch, laid out so original_name == <label>/<source path>
# ---------------------------------------------------------------------------------------------

def farm_source(e):
    if LOCAL:
        return local_path(e["relpath"])
    if e["kind"] == "loose":
        return staged_path(e["drive"], e["relpath"])
    return os.path.join(EXTRACT, archive_key(e["drive"], e["archive"]), e["member"].replace("/", "\\"))


def farm_target(e):
    return os.path.join(FARM, e["batch"], e["original_name"].replace("/", "\\"))


def prune_farm(exp):
    """Remove farm entries the current plan no longer places there (a re-plan moved or dropped
    them). Only a HARD LINK is removed -- st_nlink >= 2 proves the staged / extracted copy still
    holds the bytes -- then empty folders. Anything else found in the farm stops the run."""
    want = {os.path.normcase(farm_target(e)) for e in exp}
    removed = 0
    for root, dirs, files in os.walk(longpath(FARM), topdown=False):
        for fn in files:
            p = os.path.join(root, fn)
            if os.path.normcase(p[4:]) in want:
                continue
            if os.stat(p).st_nlink < 2:
                raise SystemExit(f"prune: {p} is not a hard link (nlink 1): refusing to delete it")
            os.remove(p)
            removed += 1
        for d in dirs:
            try:
                os.rmdir(os.path.join(root, d))
            except OSError:
                pass  # not empty
    print(f"prune: removed {removed} farm links no longer in the plan")


def cmd_farm(args):
    exp = load_expected(args.out)
    if args.prune:
        prune_farm(exp)
    if args.batch:
        exp = [e for e in exp if e["batch"] in set(args.batch)]
    made = kept = errs = 0
    for e in exp:
        src, dst = longpath(farm_source(e)), longpath(farm_target(e))
        try:
            if os.path.exists(dst):
                if os.path.samefile(src, dst):
                    kept += 1
                    continue
                raise RuntimeError(f"farm path exists and is NOT a link to its source: {dst}")
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            os.link(src, dst)
            made += 1
        except Exception as ex:  # tallied, never swallowed
            errs += 1
            print(f"  ERROR {e['original_name']}: {type(ex).__name__}: {ex}")
    # nothing else may sit in a batch's farm: the engine globs **/*.czi
    stray = 0
    want = {os.path.normcase(farm_target(e)) for e in exp}
    for b in sorted({e["batch"] for e in exp}):
        for root, _d, files in os.walk(longpath(os.path.join(FARM, b))):
            for fn in files:
                p = os.path.join(root, fn)[4:]
                if os.path.normcase(p) not in want:
                    stray += 1
                    print(f"  STRAY {p}")
    print(f"farm: {made} linked, {kept} already linked, {errs} errors, {stray} stray files")
    if errs or stray:
        raise SystemExit(1)


# ---------------------------------------------------------------------------------------------
# configs: one YAML + one case table per batch (committed)
# ---------------------------------------------------------------------------------------------

CASE_COLS = ["original_name", "drv_project", "drv_researcher", "drv_operator", "drv_subject_alias",
             "drv_subject_animal", "drv_sample_id", "drv_sample_type", "drv_link_name", "drv_notes",
             "drv_sha256", "drv_claim", "drv_acq_group", "drv_acq_group_n"]

YAML = """\
# Historical microscopy drives -- batch {batch}: {instrument}, {files} files, {gb} GB ({bucket}).
# Projects: {projects}
#
# GENERATED by tools/drive_staging/ingest_plan.py configs ({generated}). Do not edit by hand:
# change the plan and re-generate. Decisions: CHANGELOG 2026-09-29 (Ryan); per-file rules and the
# dry-run review: tasks/drives_ingest_dryrun_review.md; procedure: tasks/drives_microscopy_ingest_runbook.md.
#
# staging_dir is a HARD-LINK FARM on D: (ingest_plan.py farm): every file sits at
# <drive-label>/<its path on the drive>, so the engine's original_name IS the traceable source path
# (e.g. drive1_FRIO-X6/Cell observer/AINHIZE/1123/.../x.czi) -- and half the dedup key. Rebuild the
# farm at the same path before any re-run. The staged copy is never modified.
#
# Project, researcher, operator, subject, sample and link name are PER FILE, from {cases} through
# auto_discover.case_table (10_TOOLS 2.1.3). A farm file with no row aborts the batch.
# acquisition_datetime is the .czi's own; the dry run proved it equal to the catalog's, file by file.
{extra}
ingest:
  delete_source_after_ingest: false
  auto_create_projects: {auto_create}

auto_discover:
  staging_dir: "{staging}"
  pattern: "**/*.czi"
  case_table:
    file: {cases}
    on_missing: error
  subject_from_db: true
  subject_lookup:
    project_alias: "${{discovered.drv_subject_alias}}"
    animal_code:   "${{discovered.drv_subject_animal}}"

registry:
  instrument:           {instrument}
  data_ecosystem:       MICROSCOPY
  instrument_model:     {model}
  modalities_in_study:  NA
  researcher:           discovered.drv_researcher
  data_source:          {data_source}
  sample_id:            discovered.drv_sample_id
  sample_type:          discovered.drv_sample_type
  acquisition_datetime: discovered.czi_acquisition_datetime
  project_name:         discovered.drv_project
  notes:                discovered.drv_notes

operator: discovered.drv_operator

link_filename: "${{discovered.drv_link_name}}"
{acp}"""

YAML_D3 = """\
# M. Jesus's drive (drive 3, MJesus-MFB, WD WX22D623YP29) -- batch {batch}: {instrument}, {files} files,
# {gb} GB ({bucket}). Projects: {projects}
#
# GENERATED by tools/drive_staging/ingest_plan.py --profile {profile} configs ({generated}). Do not
# edit by hand: change the plan and re-generate. The gate, its decisions and the production procedure:
# {review_doc}. Rules: Ryan 2026-09-29 (claims, instrument by device serial), 2026-09-30
# (this drive), 2026-10-01 (raw vs derivative).
#
# staging_dir is a HARD-LINK FARM on D: (ingest_plan.py farm) into a LOCAL MIRROR of the staged copy
# (ingest_plan.py localize: copied once from J:\\_staging_drive3_MJ\\, every file's SHA-256 checked against
# the drive manifest). Every file sits at <drive-label>/<its path on the drive>, so the engine's
# original_name IS the traceable source path (drive3_MJesus-MFB/Microscopio/.../x.czi) -- and half the
# dedup key. Rebuild the farm at the same path before any re-run. The staged copy is never modified.
#
# Project, researcher, operator, subject, sample and link name are PER FILE, from {cases} through
# auto_discover.case_table (10_TOOLS 2.1.3). A farm file with no row aborts the batch. This ingest creates
# and reopens no project. acquisition_datetime is the .czi's own.
{extra}
ingest:
  delete_source_after_ingest: false
  auto_create_projects: false

auto_discover:
  staging_dir: "{staging}"
  pattern: "**/*.czi"
  case_table:
    file: {cases}
    on_missing: error
  subject_from_db: true
  subject_lookup:
    project_alias: "${{discovered.drv_subject_alias}}"
    animal_code:   "${{discovered.drv_subject_animal}}"

registry:
  instrument:           {instrument}
  data_ecosystem:       MICROSCOPY
  instrument_model:     {model}
  modalities_in_study:  NA
  researcher:           discovered.drv_researcher
  data_source:          {data_source}
  sample_id:            discovered.drv_sample_id
  sample_type:          discovered.drv_sample_type
  acquisition_datetime: discovered.czi_acquisition_datetime
  project_name:         discovered.drv_project
  notes:                discovered.drv_notes

operator: discovered.drv_operator

link_filename: "${{discovered.drv_link_name}}"
"""

ACP_0118 = """
auto_create_project:
  owner:       "Data-Office"
  description: "Animal protocol AE-biomaGUNE-0118 (rat; `Proyecto 0118 Monocrotalina`). Created by the 2026 historical-drives ingest for the Cell Observer histology filed as `118 LUCIA` (the (A) correction 118 -> 0118, approved 2026-09-29)."
  notes:       "Subject ids HELD until the researcher confirms the 118 -> 0118 reading (CHANGELOG 2026-09-29). Owner is a placeholder: edit _project.yaml."
"""

EXTRA_0118 = """#
# THE ONLY BATCH THAT CREATES A PROJECT: AE-biomaGUNE-0118 (the (A) correction of `118 LUCIA`,
# approved 2026-09-29). Its 12 subject ids are deliberately HELD (blank) until Lucia confirms.
"""
EXTRA_XMIC = """#
# XMIC = the Charite Axio Imager.Z2 (device serial 784053): external data, like XMRI. The
# instrument model is written literally; data_source records the origin.
"""
EXTRA_XMIC_D3 = """#
# XMIC = Biodonostia's ZEISS Axioscan 7 (device serial 4661000340; ours, ZWSI, is 4661000718): external
# data, like XMRI and the Charite Axio Imager.Z2. A PhD student of the group scanned M. Jesus's slides there,
# with no formal collaboration (Irene, 2026-10-08). The instrument model is written literally; data_source records
# the origin; the researcher is M. Jesus (`MJ`, Ryan 2026-10-08); the operator stays blank (her surname is unknown):
# each row's note says who scanned it. Projects include the slide-label readings L1 and L2 (Ryan, 2026-10-08).
"""
EXTRA_CLOSED = """#
# !! TARGET PROJECT IS CLOSED (folder deleted 2026-07-14). Do NOT run until the coordinator has
# decided to reopen it: Step 12 would otherwise re-create projects/<name>/raw_linked/ alone.
"""
EXTRA_BMJ = """#
# !! biomaGUNE MJ: the files whose only copy (or whose canonical copy) sits in M. Jesus's own
# `biomaGUNE MJ` folder. Ryan ordered that folder LAST: this batch runs after C01-C04 have all been run and
# verified (the coordinator, 2026-10-06; tasks/drive3_czi_gate.md G2).
"""


def cmd_configs(args):
    exp = load_expected(args.out)
    batches = list(rcsv(os.path.join(args.out, "batches.csv")))
    os.makedirs(args.config_dir, exist_ok=True)
    generated = dt.date.today().isoformat()
    for b in batches:
        es = sorted((e for e in exp if e["batch"] == b["batch"]), key=lambda e: e["original_name"])
        inst = b["instrument"]
        cases = f"cases_{b['batch']}.csv"
        wcsv(os.path.join(args.config_dir, cases), CASE_COLS, (
            {"original_name": e["original_name"], "drv_project": e["project"],
             "drv_researcher": e["researcher"], "drv_operator": e["operator"],
             "drv_subject_alias": e["subject_alias"], "drv_subject_animal": e["subject_animal"],
             "drv_sample_id": e["sample_id"], "drv_sample_type": e["sample_type"],
             "drv_link_name": e["link_name"], "drv_notes": e["notes"], "drv_sha256": e["sha256"],
             "drv_claim": e["verdict"], "drv_acq_group": e.get("acq_group", ""),
             "drv_acq_group_n": e.get("acq_group_n", "")} for e in es))
        staging = os.path.join(FARM, b["batch"]).replace("\\", "/")
        if SAME_ACQ_MODE == "decide":
            text = YAML_D3.format(
                batch=b["batch"], instrument=inst, files=b["files"], gb=b["gb"], bucket=b["bucket"],
                projects=b["projects"], generated=generated, cases=cases, profile=PROFILE_NAME,
                review_doc=PROFILE["review_doc"],
                extra=(EXTRA_BMJ if b["bucket"] == "CELL-biomaGUNE-MJ" else "")
                + (EXTRA_XMIC_D3 if inst == "XMIC" else ""),
                staging=staging,
                model=f'"{XMIC_MODEL}"' if inst == "XMIC" else "discovered.czi_microscope_name",
                data_source=f'"{XMIC_SOURCE}"' if inst == "XMIC" else "internal")
        else:
            extra = EXTRA_0118 if b["bucket"] == "CELL-0118" else EXTRA_XMIC if inst == "XMIC" else \
                EXTRA_CLOSED if b["bucket"].startswith("CELL-closed") else ""
            text = YAML.format(
                batch=b["batch"], instrument=inst, files=b["files"], gb=b["gb"], bucket=b["bucket"],
                projects=b["projects"], generated=generated, cases=cases, extra=extra,
                auto_create="true" if b["auto_create"] == "Y" else "false",
                staging=staging,
                model=f'"{XMIC_MODEL}"' if inst == "XMIC" else "discovered.czi_microscope_name",
                data_source=f'"{XMIC_SOURCE}"' if inst == "XMIC" else "internal",
                acp=ACP_0118 if b["auto_create"] == "Y" else "")
        with open(os.path.join(args.config_dir, f"{CONFIG_PREFIX}{b['batch']}.yaml"), "w", encoding="utf-8",
                  newline="\n") as f:
            f.write(text)
    with open(os.path.join(args.config_dir, "batches.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(batches[0].keys()))
        w.writeheader()
        w.writerows(batches)
    print(f"{len(batches)} configs -> {args.config_dir}")


# ---------------------------------------------------------------------------------------------
# scratch: a throwaway NAS root for the end-to-end rehearsal (never production)
# ---------------------------------------------------------------------------------------------

def cmd_scratch(args):
    """Copy production's registries (read-only on J:) into a fresh scratch root and give every
    existing project the rehearsal batches touch a folder whose raw_linked\\ holds a zero-byte
    stand-in for each name production already uses -- so a link-name collision in the rehearsal
    is real and is caught (a stand-in is never the same file as the new raw primary)."""
    import shutil
    root = args.root
    if os.path.exists(root):
        raise SystemExit(f"{root} exists: remove it first (it is scratch; never point this at J:)")
    if os.path.normcase(os.path.abspath(root)).startswith(os.path.normcase(os.path.abspath(args.nas))):
        raise SystemExit("the scratch root may not live under the production NAS root")
    if os.path.splitdrive(os.path.abspath(root))[0].lower() == os.path.splitdrive(os.path.abspath(args.nas))[0].lower():
        raise SystemExit("the scratch root may not live on the production NAS drive")
    reg_src = os.path.join(args.nas, "registries")
    reg_dst = os.path.join(root, "registries")
    os.makedirs(reg_dst)
    for fn in os.listdir(reg_src):
        if fn.endswith(".csv") or fn == ".acq_id_seq.json":
            shutil.copy2(os.path.join(reg_src, fn), os.path.join(reg_dst, fn))
    for d in ("raw", "projects"):
        os.makedirs(os.path.join(root, d))
    exp = [e for e in load_expected(args.out) if e["batch"] in set(args.batch or [])]
    projects = load_projects(args.nas)
    for name in sorted({e["project"] for e in exp if e["project"]}):
        p = projects.get(name.lower())
        if not p:
            continue  # created by the rehearsal itself (drives 1+2: 0118)
        folder = os.path.join(root, p["folder"].strip("/").replace("/", "\\"))
        os.makedirs(os.path.join(folder, "raw_linked"), exist_ok=True)
        src_links = os.path.join(args.nas, p["folder"].strip("/").replace("/", "\\"), "raw_linked")
        n = 0
        for fn in (os.listdir(src_links) if os.path.isdir(src_links) else []):
            open(os.path.join(folder, "raw_linked", fn), "wb").close()
            n += 1
        print(f"  {name}: folder + {n} stand-in link names")
    print(f"scratch NAS ready at {root}")


def main():
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--profile", default=DEFAULT_PROFILE)
    known, _rest = pre.parse_known_args()
    use_profile(known.profile)
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--profile", default=DEFAULT_PROFILE, choices=sorted(PROFILES))
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--nas", default=NAS, help="production NAS root, read-only here")
    ap.add_argument("--farm", default=None, help="another farm root (a variant's check); default the profile's")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("goptical")
    g.add_argument("--hash", action="store_true")
    pl = sub.add_parser("plan")
    pl.add_argument("--config-dir", default=CONFIG_DIR, help="where readings.csv / label_readings.csv are read")
    sub.add_parser("extract")
    lo = sub.add_parser("localize")
    lo.add_argument("--rehash", action="store_true", help="re-hash files already in the local mirror")
    lo.add_argument("--subset", choices=["all", "pixel"], default="all",
                    help="pixel: only the planned members of the pixel-check groups (they are needed first)")
    lo.add_argument("--batch", action="append", help="only these batches")
    vl = sub.add_parser("verify-local")
    vl.add_argument("--subset", choices=["all", "pixel"], default="all")
    vl.add_argument("--batch", action="append", help="only these batches")
    vl.add_argument("--workers", type=int, default=3)
    f = sub.add_parser("farm")
    f.add_argument("--batch", action="append")
    f.add_argument("--prune", action="store_true", help="first remove farm links the plan no longer places")
    c = sub.add_parser("configs")
    c.add_argument("--config-dir", default=CONFIG_DIR)
    sc = sub.add_parser("scratch")
    sc.add_argument("--root", default=SCRATCH_ROOT)
    sc.add_argument("--batch", action="append")
    args = ap.parse_args()
    if args.farm:
        global FARM
        FARM = args.farm
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    {"goptical": cmd_goptical, "plan": cmd_plan, "extract": cmd_extract, "localize": cmd_localize,
     "verify-local": cmd_verify_local, "farm": cmd_farm, "configs": cmd_configs,
     "scratch": cmd_scratch}[args.cmd](args)


if __name__ == "__main__":
    main()
