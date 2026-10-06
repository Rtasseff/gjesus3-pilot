#!/usr/bin/env python3
"""project_claims.py -- classify every project claim on the two staged historical-microscopy drives.

READ-ONLY. It reads the two staged manifests, lists (never extracts) the archives, reads the
production registries on J:\\ and runs SELECTs against the animal-facility DB through
tools/animal_db.py. It writes only to OUT (default D:\\projects\\gjesus3\\staging\\_analysis\\codes\\).

    python tools/drive_staging/project_claims.py              # full run (~2 min once archives are cached)
    python tools/drive_staging/project_claims.py --relist     # re-list archive members (slow: LEONE.zip)
    python tools/drive_staging/project_claims.py --fresh-db   # ignore the DB lookup cache

Outputs (all regenerable):
    claims.csv               one row per claim: token, where it sits, verdict, evidence
    file_claims.csv          one row per manifest file (78,839): the claim it inherits and why
    archive_member_claims.csv one row per member of every archive that holds a claim
    noclaim_groups.csv       unclaimed files grouped by (researcher, series), for a human to map
    rejected_tokens.csv      every number-like token that was NOT treated as a claim, with the reason
                             (7+ digit runs are logged by length: they can never be a 3-4 digit code)
    safety_net.csv           rejected tokens whose value is nevertheless a valid protocol code
    archive_members.json     cache of archive listings (keyed by sha256)
    db_cache.json            cache of (protocol, animal) lookups -- found / not_found only
    run_summary.txt          counts, for the findings document

WHAT A CLAIM IS
---------------
A 3-4 digit token in a folder name, a filename or an archive member path that sits where a
project id sits: `Proyecto 0522`, `project0420`, a folder named `1123` or `1022 TUMORES`, a chunk in
`Irene_0522_Metfor`, the code slot of `MFB_AUA_1123_ID239Lu_HE_10x.czi`, a code next to an animal
(`ID10_1123_TM_10x.czi`, `jrc220622_m1_1321_1_1`, `m13_0320_NIFTI`).

Everything else that looks like a number is REJECTED and logged with its reason: dates (masked
first, so `230519` never yields `2305`), years, AxioScan auto-name counters, animal numbers,
magnifications, wavelengths, time points, digits inside names (`ki67`, `TOM20`, `A549`), Bruker
`pdata` numbers, DICOM UIDs, and numbered sibling series (animal/sample ids such as `7822`, `8170`,
or `1024 1025 1026 1027`). `CONTEXT_RULES` below holds the few tree-specific judgements, each with
its reason, so a reviewer can see and overrule them.

HOW A CLAIM IS DECIDED (Ryan, 2026-09-29)
-----------------------------------------
Resolving in the DB is necessary, not sufficient (the PROJ-0056 lesson):
  CONFIRMED  the code is a valid protocol AND the bulk of its files' animals exist in it AND its raw
             imaging does not predate the protocol's first animal / start AND nothing contradicts it.
  A          the code does not resolve, and EXACTLY ONE typo candidate (one digit changed, adjacent
             swap, missing leading zero, 3<->4 digits) passes STRICT checks with animal-level
             evidence (>=80% of animals found, no date contradiction at all).
  B          positioned and phrased as a project id, does not resolve, no correction passes, and
             (unless keyword-phrased) it does not read as a date near its files' dates:
             new project `Project-<code as written>`, no animal link.
  C          everything else plausibly a claim: blank project, listed for Ryan.
A DB outage is never read as "not found": an `unreachable` lookup aborts the run.

PER FILE, after the claim verdict: a file inherits the NEAREST claim above it (its claim root). It
drops to C on its own if ITS animal is not in the protocol, or it is dated before that animal's
birth, or (raw imaging) before the protocol's first animal. When nested claims disagree and the
file's animal exists in both protocols, the DB's own dates decide: the one protocol that logs a
procedure on that animal within 3 days of the acquisition, else the one whose animal was already
born; otherwise C. Dates checked are raw-imaging only (`is_data`): paperwork legitimately predates.

TIE-BREAK FOR HISTOLOGY (Ryan, 2026-09-29, approved reading of the (C) cases). For a microscopy
file (`HISTOLOGY_EXT`) whose animal exists in several protocols, and which the two rules above do
not separate, the DB decides if EXACTLY ONE candidate's animal has a terminal procedure (`Organ
sampling` or `Perfusion`, `TERMINAL_PROC_RE`) dated on or before the file date: a slide is cut
after the tissue is taken. The born-by-date rule is then re-checked, and a disagreement between
the two leaves the file (C). The rule only ever CONFIRMS the file's nearest claim, never
overrules it: the DB logs sampling unevenly, so a missing terminal procedure is not evidence
(1321's animals 98-101 have slides on the drives and no sampling logged). It is NOT applied to in-vivo data (MRI/PET/CT/NIfTI): there a
prior perfusion is evidence AGAINST an animal, which is how the four `jrc220622_m*_1321` studies
inside `Cursosurf_0219` were decided. Procedure dates before 1990 are ignored (the DB holds
`0023-08-07`-style typos).

The researcher is the innermost whole-segment person-named folder (hub brief 8.7); names embedded
in longer folder names are flagged, not assigned; operator initials (AUA, MBC, MJS) are never
mapped to a person. Findings and the reasoning behind every rule: tasks/drives_project_codes_findings.md
"""
import argparse
import collections
import csv
import datetime as dt
import json
import os
import re
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
sys.path.insert(0, TOOLS)
import animal_db  # noqa: E402
from ni_gnuclear_discover import valid_protocol_codes, AE_CODE_RE  # noqa: E402

STAGING = r"D:\projects\gjesus3\staging"
DRIVES = {
    "drive1": "drive1_FRIO-X6_2322E4A111E7",
    "drive2": "drive2_MFB-Disco-2_2322E4A112BD",
}
REGISTRIES = r"J:\gjesus3-data\registries"
SEVENZ = r"C:\Program Files\7-Zip\7z.exe"
LONG = "\\\\?\\"  # the \\?\ long-path prefix; asserted below because heredocs have mangled it before
assert LONG == "\\" + "\\" + "?" + "\\", repr(LONG)

# ---------------------------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------------------------

# Whole-segment person names seen on the drives (name as written; matched case-insensitively).
# Only a WHOLE segment is a person folder. A name embedded in a longer folder name is flagged, not
# assigned. Initials (AUA, MBC, MJS, MJ, IAZ, EO) are deliberately absent: Ryan deferred them.
PERSON_NAMES = [
    "AINHIZE", "Lydia", "Laura", "Maria Jesus", "María Jesús", "Marta", "Lucia-Lorena Garayoa",
    "Lucia", "Lucía", "HUGO", "Claudia", "Itziar", "MARINA", "MANON", "Asier", "Irene", "Ekine",
    "Amanda", "Irati", "Elena", "Amaia", "Ana B", "Haizpea", "Iraia", "Julen", "Libe", "Nicola",
    "Peio", "Piotr", "Zuriñe", "Naiara", "Gabriela", "Susana", "Catarina", "Juliana", "Sergio",
    "Ruben", "Rubén", "Liuda", "Irantzu", "Krishna", "Ignacio",
]
_PERSON_LC = {p.lower(): p for p in PERSON_NAMES}
# Levels whose immediate child is "the person" (hub brief 8.7), and where a mixed name such as
# `HUGO HE` or `Lydia TAX LEASE_Marta` is read as its leading person name, flagged.
PERSON_LEVEL_PARENTS = {("drive1", ("Cell observer",)), ("drive1", ("Former students",)),
                        ("drive2", ("CELL OBSERVER 2",))}
# Drive-root folders/archives that belong to one person, with the evidence for it.
ROOT_OWNERS = {
    ("drive2", "2025-10-02 - Toshiba EXT (Backup)"): (
        "Laura",
        "backup of one person's drive: Proyectos_Laboratorio_Laura, TEM-Laura, "
        "Papeleo\\Admision doctorado\\Training_Laura-2023, TESIS, CV, Visa, Padron"),
    ("drive1", "Claudia"): ("Claudia", "drive-root folder named for the person"),
    ("drive1", "Haizpea_2020-2022.7z"): ("Haizpea", "archive named for the person"),
    ("drive1", "Drive zuri 170823.zip"): (
        "zuri", "archive named for the person; same content as Former students\\Zuriñe "
        "(not normalised: the registry's researcher convention is with the group)"),
}
TWO_PERSON_ROOTS = {("drive1", "Drive Maria Jesus and Irati 20211209.zip"): "Maria Jesus; Irati"}

# Tree-specific judgements. (drive or None, path regex, reason). A 3-4 digit token inside a
# matching path is rejected with the reason. Each one was checked by hand on 2026-09-29.
CONTEXT_RULES = [
    (None, r"(?:Zuriñe|Drive zuri 170823)[\\/]",
     "zuri-animal-number: Zuriñe's 4-digit numbers are mouse ids (`8170 y 8171`, `8244 y 45`, "
     "`7822 10x-1 confocal`, CDH5-JAGGED colony); none resolves, all sit in C/EXP BLEO/PBS groups"),
    (None, r"Muestras hospital clinic",
     "human-sample-id: hospital clinical samples (`ZB.PR-004`, `ZB.18/203`), no animal protocol"),
    (None, r"[\\/]Iraia[\\/](?:GSEA|GO|Cytoscape|R|Excels)",
     "analysis-output-number: GSEA/GO enrichment output (gene-set sizes, run ids)"),
    (None, r"[\\/]Nicola[\\/]Chem Lab[\\/]", "chemistry-sample-number: NMR/polymer sample numbering"),
    (None, r"(?:Fiji\.app|[\\/]Origin[\\/]|Sandbox[\\/]GraphPad|\$RECYCLE\.BIN|\.Spotlight-V100|\.fseventsd)",
     "software-or-system: installed software, recycle bin or OS index"),
    (None, r"LEONE[\\/]", "leone-case-number: LIONS cohort case/series numbering (LEONE 304, S69460)"),
]
_CONTEXT_RULES = [(d, re.compile(p, re.I), r) for d, p, r in CONTEXT_RULES]

WAVELENGTHS = {"405", "488", "546", "555", "561", "568", "594", "633", "640", "647", "660"}
KEYWORDS = {"proyecto", "project", "proy", "proj", "protocolo", "protocol", "pr"}
CELL_LINES = re.compile(r"(?i)^(?:A549|MDA|MB|231|THP|HepG2|hPAEpC|HLF|HUVEC|NIH3T3|3T3|U87|GL261)$")

AE_CODE_RE_I = re.compile(AE_CODE_RE.pattern, re.I)
UID_RE = re.compile(r"^\d+(?:\.\d+){3,}$")
GUID_RE = re.compile(r"^[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}$", re.I)

# Masks, applied in order; each masked span is logged as a rejected token with its reason.
MASKS = [
    ("axioscan-auto-name", re.compile(
        r"(?<!\d)(?:19|20)\d{2}_\d{2}_\d{2}__\d{2}_\d{2}__\d{4}(?!\d)")),
    ("date-iso", re.compile(
        r"(?<!\d)(?:19|20)\d{2}[-_.](?:0?[1-9]|1[0-2])[-_.](?:0?[1-9]|[12]\d|3[01])(?!\d)")),
    ("date-dmy", re.compile(
        r"(?<![\d.])(?:0?[1-9]|[12]\d|3[01])[-_.](?:0?[1-9]|1[0-2])[-_.](?:\d{4}|\d{2})(?![\d.])")),
    ("date-8digit", re.compile(r"(?<!\d)(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])(?!\d)")),
    ("date-or-time-6digit", re.compile(r"(?<!\d)\d{6}(?!\d)")),
    ("long-number", re.compile(r"(?<!\d)\d{7,}(?!\d)")),
    ("animal-id-range", re.compile(r"(?i)(?<![A-Za-z])ID\s*\d+\s*[-–]\s*(?:ID\s*)?\d+")),
    ("animal-id", re.compile(r"(?i)(?<![A-Za-z])ID\s*\d+(?:[.,]\d+)?[A-Za-z]*")),
    ("animal-m-number", re.compile(r"(?<![A-Za-z\d])m\d{1,4}(?![A-Za-z\d])")),
    ("rat-number", re.compile(r"(?<![A-Za-z\d])R\d{3}-\d{2}(?!\d)")),
    ("magnification", re.compile(r"(?i)(?<![A-Za-z\d])\d+(?:[.,]\d+)?\s?x\d*(?![A-Za-z])")),
    # single-letter units only when glued to the number: `0619 m17` must NOT read as "0619 m"
    ("timepoint", re.compile(r"(?i)(?<![A-Za-z\d])\d+(?:h|min|d|w|m)(?![A-Za-z\d])"
                             r"|(?<![A-Za-z\d])\d+\s?(?:hours?|days?|weeks?|months?|meses|semanas|dias)(?![A-Za-z])")),
    ("size-unit", re.compile(r"(?<![A-Za-z\d])\d+(?:nm|um|µm|mm|ng|ug|mg|ml|ul|mM|uM|nM|kX|kx)(?![A-Za-z])")),
    ("version-number", re.compile(r"(?i)\bv\.?\d+(?:\.\d+)+")),
]
AXIO_SUFFIX_RE = re.compile(r"(?<!\d)(?:19|20)\d{2}_\d{2}_\d{2}__\d{2}_\d{2}__\d{4}_(\d{1,3})([A-Za-z]{1,3})\b")
SPLIT_RE = re.compile(r"[\s_\-.,()+&\[\]{}'´;:!#=~]+")
PREFIXED_CODE_RE = re.compile(r"(?i)^(proyecto|project|proj|pr|mri)(\d{3,4})$")
MFB_RE = re.compile(r"(?i)^MFB[_-]([A-Za-z]+)[_-](\d{3,4})[_-]")

# Animal tokens usable for the DB cross-check (kind, regex). The organ letters that follow an id
# (`ID239Lu`, `ID10H`) are anatomy, never part of the animal number.
ANIMAL_TOKEN_RES = [
    ("ID", re.compile(r"(?i)(?<![A-Za-z])ID\s*(\d{1,4})(?:[.,]\d+)?([A-Za-z]*)(?![\d])")),
    ("m", re.compile(r"(?<![A-Za-z\d])m(\d{1,4})(?![A-Za-z\d])")),
]


def is_person(seg):
    return seg.strip().lower() in _PERSON_LC


def leading_person(seg):
    s = seg.strip()
    for p in sorted(PERSON_NAMES, key=len, reverse=True):
        if re.match(r"(?i)^" + re.escape(p) + r"(?![A-Za-zñÑáéíóú])", s):
            return s[:len(p)]
    return None


def embedded_persons(seg):
    out = []
    for p in PERSON_NAMES:
        if re.search(r"(?i)(?<![A-Za-zñÑáéíóú])" + re.escape(p) + r"(?![A-Za-zñÑáéíóú])", seg) \
                and seg.strip().lower() != p.lower():
            out.append(p)
    return out


# ---------------------------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------------------------

def load_manifest(drive):
    path = os.path.join(STAGING, DRIVES[drive], "manifest.csv")
    rows = {}
    with open(path, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            rows[r["relpath"]] = r  # last row per relpath wins (the manifest appends on resume)
    return rows


def list_archive(drive, relpath):
    """Return ([(member_path, size, iso_datetime)], error_or_None). Lists; never extracts."""
    full = LONG + os.path.join(STAGING, DRIVES[drive], "files", relpath)
    members = []
    if relpath.lower().endswith(".zip"):
        try:
            with zipfile.ZipFile(full) as z:
                for i in z.infolist():
                    if i.is_dir():
                        continue
                    try:
                        when = dt.datetime(*i.date_time).isoformat()
                    except ValueError:
                        when = ""
                    members.append((i.filename, i.file_size, when))
            return members, None
        except Exception as e:  # truncated archives fall through to 7-Zip
            zerr = f"zipfile {type(e).__name__}: {e}"
    else:
        zerr = None
    p = subprocess.run([SEVENZ, "l", "-slt", "-ba", full], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    cur = {}
    for line in p.stdout.splitlines() + [""]:
        if line.startswith("Path = "):
            cur = {"path": line[7:]}
        elif " = " in line and cur:
            k, v = line.split(" = ", 1)
            cur[k] = v
        elif line == "" and cur:
            if cur.get("Folder") != "+" and "D" not in cur.get("Attributes", "")[:1]:
                try:
                    size = int(cur.get("Size") or 0)
                except ValueError:
                    size = 0
                members.append((cur["path"], size, (cur.get("Modified") or "").replace(" ", "T")[:19]))
            cur = {}
    err = None
    if p.returncode != 0 or zerr:
        err = "; ".join(x for x in [zerr, f"7z rc={p.returncode}: {p.stderr.strip()[:300]}"] if x)
    return members, err


def load_archives(manifests, out_dir, relist):
    cache_path = os.path.join(out_dir, "archive_members.json")
    cache = {}
    if os.path.isfile(cache_path) and not relist:
        with open(cache_path, encoding="utf-8") as f:
            cache = json.load(f)
    result, changed = {}, False
    for drive, rows in manifests.items():
        for rp, r in rows.items():
            if not re.search(r"(?i)\.(zip|7z|rar)$", rp):
                continue
            key = f"{drive}|{rp}"
            if re.search(r"(?i)downloadly|[\\/]Origin[\\/]|ok\.dll\.zip", rp):
                result[key] = {"sha256": r["sha256"], "members": [], "err": None,
                               "skipped": "software installer / crack archive (hub brief 7.4): not listed"}
                continue
            c = cache.get(key)
            if c and c.get("sha256") == r["sha256"]:
                result[key] = c
                continue
            print(f"  listing {key} ...", file=sys.stderr)
            members, err = list_archive(drive, rp)
            result[key] = {"sha256": r["sha256"], "members": members, "err": err, "skipped": None}
            changed = True
    if changed or not os.path.isfile(cache_path):
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(result, f)
    return result


def load_registry():
    def rd(name):
        with open(os.path.join(REGISTRIES, name), encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    projects = {r["name"].lower(): r["project_id"] for r in rd("registry_projects.csv")}
    subjects = collections.defaultdict(set)
    for r in rd("registry_subjects.csv"):
        try:
            subjects[r["project_alias"]].add(int(r["animal_code"]))
        except ValueError:
            pass
    return projects, subjects


# ---------------------------------------------------------------------------------------------
# DB (read-only, through animal_db)
# ---------------------------------------------------------------------------------------------

class DB:
    def __init__(self, out_dir, fresh):
        self.conn = animal_db.get_connection()
        self.valid = set(valid_protocol_codes(self.conn))
        self.cache_path = os.path.join(out_dir, "db_cache.json")
        self.cache = {}
        if os.path.isfile(self.cache_path) and not fresh:
            with open(self.cache_path, encoding="utf-8") as f:
                self.cache = json.load(f)
        self.lookups = 0
        self.proto = self._protocols()

    def _protocols(self):
        """code -> dob_min (ignoring the 1970 placeholder), dob_max, proc_min, proc_max, n, start, end."""
        out = {}
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT p.id, p.project_code, p.projectAlias, p.start_date, p.end_date, "
                "  (SELECT MIN(a.date_of_birth) FROM animals a WHERE a.id_project=p.id "
                "     AND a.date_of_birth > '1990-01-01') AS dob_min, "
                "  (SELECT MAX(a.date_of_birth) FROM animals a WHERE a.id_project=p.id) AS dob_max, "
                "  (SELECT COUNT(*) FROM animals a WHERE a.id_project=p.id) AS n, "
                "  (SELECT MAX(a.animal_code) FROM animals a WHERE a.id_project=p.id) AS code_max, "
                "  (SELECT MIN(ap.date) FROM animal_procedures ap JOIN animals a ON a.id=ap.id_animal "
                "     WHERE a.id_project=p.id AND ap.date > '1990-01-01') AS proc_min, "
                "  (SELECT MAX(ap.date) FROM animal_procedures ap JOIN animals a ON a.id=ap.id_animal "
                "     WHERE a.id_project=p.id) AS proc_max "
                "FROM projects p")
            for r in cur.fetchall():
                codes = set()
                alias = (r.get("projectAlias") or "").strip()
                if re.fullmatch(r"\d{3,4}", alias):
                    codes.add(alias)
                codes.update(AE_CODE_RE.findall(r.get("project_code") or ""))
                for c in codes:
                    out[c] = {k: (v.isoformat()[:10] if hasattr(v, "isoformat") else v)
                              for k, v in r.items()}
        return out

    def lookup(self, code, animal):
        key = f"{code}|{int(animal)}"
        if key in self.cache:
            return self.cache[key]
        res = animal_db.lookup(code, int(animal), conn=self.conn, use_cache=False)
        self.lookups += 1
        if res.status == "unreachable":
            # Never read an outage as "not in the DB": that would turn a Confirmed into a (B).
            raise RuntimeError(f"animal DB unreachable during lookup {key}: {res.detail}")
        val = {"status": res.status}
        if res.status == "found":
            s = res.subject
            val.update(subject_id=s["facility_animal_id"], dob=s["date_of_birth"],
                       procs=[(p["date"], p["type"]) for p in s["procedures"]],
                       species=s["species"], sex=s["sex"])
        self.cache[key] = val
        return val

    def save(self):
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(self.cache, f)


# ---------------------------------------------------------------------------------------------
# Tokenising one path segment
# ---------------------------------------------------------------------------------------------

class Rejects:
    """Aggregated rejected-token log: (token, reason, source) -> count, example."""

    def __init__(self):
        self.d = {}

    def add(self, token, reason, source, example):
        if reason == "long-number":
            # 7+ digit runs (DICOM instance numbers, timestamps) can never be a 3-4 digit code;
            # logged by length so the file stays readable (was 539k distinct values)
            token = f"<{len(token)}-digit number>"
        k = (token, reason, source)
        if k in self.d:
            self.d[k][0] += 1
        else:
            self.d[k] = [1, example]


def context_rule(drive, fullpath):
    for d, rx, reason in _CONTEXT_RULES:
        if (d is None or d == drive) and rx.search(fullpath):
            return reason
    return None


def analyse_segment(seg, is_file, prev_segs, sibling_series, rejects, example, drive, ctx_reason,
                    ancestor_claim=False):
    """Return list of candidate dicts {token, phrasing, pos} from one segment; log the rest.

    `prev_segs` are the segments above (for the pdata rule); `sibling_series` is True when this
    bare-number folder is one of a numbered sibling series.
    """
    source = "filename" if is_file else "folder"
    stem = re.sub(r"\.[A-Za-z0-9]{1,6}$", "", seg) if is_file else seg
    if is_file and stem.lower().endswith(".tif"):
        stem = stem[:-4]
    if not is_file and stem.endswith(".tif_files"):
        stem = stem[: -len(".tif_files")]
    cands = []

    if UID_RE.match(stem) or GUID_RE.match(stem) or stem.startswith("S-1-5-"):
        rejects.add(stem[:40], "dicom-uid-or-system-id", source, example)
        return cands

    # AE-biomaGUNE-NNNN anywhere is a claim by construction (the anchored regex; case-insensitive
    # here because `AE-biomagune-0721_v3.docx` is how people type it).
    for m in AE_CODE_RE_I.finditer(stem):
        cands.append({"token": m.group(1), "phrasing": "keyword:AE-biomaGUNE", "pos": m.start()})
    masked = AE_CODE_RE_I.sub(lambda m: " " * len(m.group(0)), stem)
    has_animal = bool(re.search(r"(?i)(?<![A-Za-z])ID\s*\d|(?<![A-Za-z\d])m\d{1,4}(?![A-Za-z\d])", stem))

    # MFB AxioScan convention: MFB_<initials>_<code>_...
    if is_file:
        m = MFB_RE.match(masked)
        if m:
            cands.append({"token": m.group(2), "phrasing": f"mfb-convention:{m.group(1)}",
                          "pos": m.start(2)})
            masked = masked[:m.start(2)] + " " * len(m.group(2)) + masked[m.end(2):]

    for reason, rx in MASKS:
        def _m(mm, reason=reason):
            rejects.add(mm.group(0), reason, source, example)
            return re.sub(r"[^\s_\-.]", "#", mm.group(0))
        masked = rx.sub(_m, masked)

    chunks = [(m.group(0), m.start()) for m in re.finditer(r"[^\s_\-.,()+&\[\]{}'´;:!#=~]+", masked)]
    words = [c for c, _ in chunks]
    for i, (c, pos) in enumerate(chunks):
        if not re.search(r"\d", c):
            continue
        prev = words[i - 1].lower() if i else ""
        nxt = words[i + 1] if i + 1 < len(words) else ""
        pm = PREFIXED_CODE_RE.match(c)
        if pm:
            tok = pm.group(2)
            if ctx_reason:
                rejects.add(tok, ctx_reason.split(":")[0], source, example)
            else:
                cands.append({"token": tok, "phrasing": f"keyword:{pm.group(1)}", "pos": pos})
            continue
        if not c.isdigit():
            if CELL_LINES.match(c):
                rejects.add(c, "cell-line", source, example)
            else:
                rejects.add(c, "digits-inside-name", source, example)
            continue
        n = len(c)
        if n <= 2:
            rejects.add(c, "short-number (index/replicate/group)", source, example)
            continue
        if n >= 5:
            rejects.add(c, "long-number", source, example)
            continue
        if n == 4 and re.fullmatch(r"(?:19[89]\d|20[0-3]\d)", c):
            rejects.add(c, "year", source, example)
            continue
        if n == 3 and c in WAVELENGTHS:
            rejects.add(c, "fluorophore-wavelength", source, example)
            continue
        if c in {"488", "555", "594", "647"}:
            rejects.add(c, "fluorophore-wavelength", source, example)
            continue
        if ctx_reason:
            rejects.add(c, ctx_reason.split(":")[0], source, example)
            continue
        if not is_file and prev_segs and prev_segs[-1].lower() == "pdata":
            rejects.add(c, "bruker-procno (folder under pdata)", source, example)
            continue
        if sibling_series and n in (3, 4) and stem == c:
            rejects.add(c, "numbered-sibling-series (animal/sample/series ids)", source, example)
            continue
        if sibling_series and i == 0:
            rejects.add(c, "numbered-sibling-series (animal/sample/series ids)", source, example)
            continue
        animal_adjacent = bool(re.match(r"(?i)^(?:ID\d|#)", nxt) or re.match(r"(?i)^#", prev)
                               or re.match(r"(?i)^m\d", nxt) or (i and re.match(r"(?i)^m\d", words[i - 1])))
        # a masked animal token appears as '#…' in the masked string; look at the raw neighbours
        raw_prev = masked[:pos].rstrip(" _-.")
        raw_next = masked[pos + n:].lstrip(" _-.")
        if raw_prev.endswith("#") or raw_next.startswith("#"):
            # neighbour was masked: is it an animal mask? check the original text around it
            around = stem[max(0, pos - 12):pos + n + 12]
            if re.search(r"(?i)(?<![A-Za-z])ID\s*\d|(?<![A-Za-z\d])m\d", around):
                animal_adjacent = True
        if prev in KEYWORDS:
            phrasing = f"keyword:{prev}"
        elif animal_adjacent:
            phrasing = "animal-paired"
        elif not is_file and stem.strip() == c:
            phrasing = "folder-exact"
        elif not is_file and i == 0:
            phrasing = "folder-head"
        elif not is_file:
            phrasing = "folder-chunk"
        elif has_animal and n == 4:
            # `0219_ctrl_ID29_lung_...czi`, `ID6B_2_0423_HE10x.czi`: code and animal in one name
            phrasing = "filename-with-animal"
        elif i == 0:
            phrasing = "filename-head"
        else:
            phrasing = "filename-chunk"
        if n == 3 and not (phrasing.startswith("keyword") or phrasing in ("folder-exact", "folder-head")):
            rejects.add(c, "three-digit-number (outside a project-id position)", source, example)
            continue
        if n == 3 and ancestor_claim and not phrasing.startswith("keyword"):
            # `1123\...\PB\102-40x`: below a claimed folder a bare 3-digit number is an animal
            rejects.add(c, "three-digit-number inside an already-claimed tree (animal/sample number)",
                        source, example)
            continue
        if c.startswith("00") and not phrasing.startswith("keyword"):
            # no protocol or group project id starts 00: `.cine_id22_.0001.jpg` is a frame counter
            rejects.add(c, "leading-00 counter/index", source, example)
            continue
        if phrasing in ("filename-chunk", "filename-head"):
            # A free 4-digit number in a filename is not a claim position on these drives (TEM
            # counters, tile sizes, GSEA ids). Logged; values that are valid codes land in safety_net.
            rejects.add(c, f"{phrasing} (not a claim position)", source, example)
            continue
        cands.append({"token": c, "phrasing": phrasing, "pos": pos})
    return cands


def animal_tokens(seg):
    """[(kind, number, raw)] animal tokens in one segment."""
    out = []
    for kind, rx in ANIMAL_TOKEN_RES:
        for m in rx.finditer(seg):
            out.append((kind, int(m.group(1)), m.group(0).strip()))
    m = AXIO_SUFFIX_RE.search(seg)
    if m:
        out.append(("axio-suffix", int(m.group(1)), m.group(1) + m.group(2)))
    if not out:
        m = re.match(r"^(\d{1,3})([A-Z][a-z]?)(?=[_\s])", seg)  # `137L_PB_20x_3.czi`
        if m:
            out.append(("lead-number", int(m.group(1)), m.group(0)))
    return out


# ---------------------------------------------------------------------------------------------
# Main pass
# ---------------------------------------------------------------------------------------------

def typo_candidates(tok):
    out = {}
    if len(tok) == 4:
        for i in range(4):
            for d in "0123456789":
                if d != tok[i]:
                    out[tok[:i] + d + tok[i + 1:]] = f"one digit changed (position {i + 1})"
        for i in range(3):
            s = tok[:i] + tok[i + 1] + tok[i] + tok[i + 2:]
            if s != tok:
                out[s] = f"adjacent digits swapped ({i + 1},{i + 2})"
        for i in range(4):
            out.setdefault(tok[:i] + tok[i + 1:], "4->3 digits (one dropped)")
    elif len(tok) == 3:
        out["0" + tok] = "missing leading zero"
        for i in range(4):
            for d in "0123456789":
                out.setdefault(tok[:i] + d + tok[i:], "3->4 digits (one inserted)")
    return out


DOC_EXT = {"doc", "docx", "pdf", "xls", "xlsx", "xlsm", "ppt", "pptx", "txt", "msg", "eml", "odt", "ods",
           "csv", "rtf", "pages", "key", "numbers", "ini", "db", "ds_store", "lnk", "url", "pzfx", "opju",
           "opj", "zip", "7z", "rar", "mat", "m", "py", "r", "json", "xml", "html", "htm", "log"}


RAW_EXT = {"czi", "lsm", "tif", "tiff", "dcm", "ima", "nii", "gz", "mhd", "raw", "img", "hdr", "nd2", "lif",
           "oib", "oir", "vsi", "svs", "ndpi", "dm4", "dm3", "jcamp", "mnova"}
BRUKER_FILES = {"2dseq", "fid", "ser", "acqp", "acqus", "method", "visu_pars", "reco", "subject", "procs"}
# Ex-vivo microscopy (slides / sections) and their image exports: the only files for which a
# terminal procedure on a candidate animal is evidence FOR that animal (tie_break, rule 2).
HISTOLOGY_EXT = {"czi", "lsm", "tif", "tiff", "png", "jpg", "jpeg", "bmp"}
TERMINAL_PROC_RE = re.compile(r"organ sampling|perfusion", re.I)


def is_data(fname):
    """Raw imaging/acquisition files: the only files whose dates are checked against a protocol's
    life. Paperwork, photos, videos and analysis legitimately predate or postdate the animals."""
    if fname.startswith("._"):
        return False
    if fname.lower() in BRUKER_FILES:
        return True
    ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ""
    if ext == "gz":
        return fname.lower().endswith(".nii.gz")
    return ext in RAW_EXT


def date_readings(tok, dates, window=45):
    """Readings of a 4-digit token as a date (DDMM, MMDD, YYMM, MMYY) within `window` days of the
    files' own dates. `2503` over files dated 2024-03-25 reads as 25-03, so it is not a project id."""
    if len(tok) != 4 or not dates:
        return []
    a, b = int(tok[:2]), int(tok[2:])
    out = []
    years = sorted({d.year for d in dates})
    for label, (mm, dd) in (("DD-MM", (b, a)), ("MM-DD", (a, b))):
        for y in years:
            try:
                d = dt.date(y, mm, dd)
            except ValueError:
                continue
            if any(abs((d - x).days) <= window for x in dates):
                out.append(f"{label} {d.isoformat()}")
                break
    for label, (yy, mm) in (("YY-MM", (a, b)), ("MM-YY", (b, a))):
        if 1 <= mm <= 12 and 10 <= yy <= 30:
            d = dt.date(2000 + yy, mm, 15)
            if any(abs((d - x).days) <= window + 15 for x in dates):
                out.append(f"{label} {d.isoformat()[:7]}")
    return out


def iso_date(s):
    try:
        return dt.date.fromisoformat(s[:10])
    except (TypeError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=os.path.join(STAGING, "_analysis", "codes"))
    ap.add_argument("--relist", action="store_true", help="re-list archive members")
    ap.add_argument("--fresh-db", action="store_true", help="ignore the DB lookup cache")
    args = ap.parse_args()
    for stream in (sys.stdout, sys.stderr):  # paths hold `Charité`, `Zuriñe`, combining accents
        stream.reconfigure(encoding="utf-8", errors="replace")
    os.makedirs(args.out, exist_ok=True)
    errors = collections.Counter()

    print("loading manifests ...", file=sys.stderr)
    manifests = {d: load_manifest(d) for d in DRIVES}
    n_manifest = sum(len(v) for v in manifests.values())
    print("listing archives ...", file=sys.stderr)
    archives = load_archives(manifests, args.out, args.relist)
    print("opening DB ...", file=sys.stderr)
    db = DB(args.out, args.fresh_db)
    reg_projects, reg_subjects = load_registry()
    rejects = Rejects()

    # ---- items: every manifest file, and every member of every listed archive -----------------
    # item = dict(drive, relpath (manifest file), member (or ''), segs (dir segments), fname,
    #             size, date, is_member)
    items = []
    for drive, rows in manifests.items():
        for rp, r in rows.items():
            parts = rp.split("\\")
            items.append({"drive": drive, "relpath": rp, "member": "", "segs": parts[:-1],
                          "fname": parts[-1], "size": int(r["size"] or 0),
                          "date": (r["mtime"] or "")[:10], "is_member": False})
    for key, a in archives.items():
        drive, rp = key.split("|", 1)
        if a.get("err"):
            errors[f"archive listing error: {key}: {a['err'][:120]}"] += 1
        parts = rp.split("\\")
        for mpath, size, when in a["members"]:
            mparts = re.split(r"[\\/]", mpath)
            items.append({"drive": drive, "relpath": rp, "member": mpath,
                          "segs": parts[:-1] + [parts[-1] + "!"] + mparts[:-1], "fname": mparts[-1],
                          "size": int(size or 0), "date": (when or "")[:10], "is_member": True})
    print(f"  {n_manifest} manifest files, {len(items) - n_manifest} archive members", file=sys.stderr)

    # ---- sibling series: parent folder -> bare-number children -------------------------------
    children = collections.defaultdict(set)
    for it in items:
        for i, s in enumerate(it["segs"]):
            children[(it["drive"], tuple(it["segs"][:i]))].add(s)
    series_parents = set()
    for key, kids in children.items():
        bare = [k for k in kids if re.fullmatch(r"\d{3,5}", k)]
        heads = [k for k in kids if re.fullmatch(r"\d{3,4}\s+(?!.*\d{4}).*", k)]
        grp = sorted({re.match(r"\d+", k).group(0) for k in bare + heads}, key=int)
        if len(grp) >= 2:
            invalid = [g for g in grp if g.zfill(4) not in db.valid]
            ints = [int(g) for g in grp]
            consecutive = any(b - a == 1 for a, b in zip(ints, ints[1:]))
            if consecutive or len(invalid) >= 2 or all(len(g) == 3 for g in grp):
                series_parents.add(key)

    # ---- per-segment analysis (memoised per unique path prefix) ------------------------------
    seg_cache = {}

    def seg_claims(drive, segs, i):
        key = (drive, tuple(segs[:i + 1]))
        if key in seg_cache:
            return seg_cache[key]
        seg = segs[i]
        full = "\\".join(segs[:i + 1])
        ctx = context_rule(drive, "\\" + full + "\\")
        seg_clean = seg[:-1] if seg.endswith("!") else seg
        is_archive_seg = seg.endswith("!")
        sib = (drive, tuple(segs[:i])) in series_parents
        anc = any(seg_claims(drive, segs, j) for j in range(i))
        cands = analyse_segment(seg_clean, is_archive_seg, segs[:i], sib, rejects,
                                f"{drive}:{full}"[:220], drive, ctx, ancestor_claim=anc)
        seg_cache[key] = cands
        return cands

    # ---- build claims -------------------------------------------------------------------------
    claims = {}          # claim_key -> claim dict
    item_chain = []      # per item: list of claim keys, outermost first (filename claim last)

    def claim_key(drive, root, token):
        return (drive, root, token)

    for it in items:
        chain = []
        for i in range(len(it["segs"])):
            for c in seg_claims(it["drive"], it["segs"], i):
                root = "\\".join(it["segs"][:i + 1])
                k = claim_key(it["drive"], root, c["token"])
                if k not in claims:
                    claims[k] = {"drive": it["drive"], "claim_root": root, "token": c["token"],
                                 "source": ("archive-member-folder" if "!" in root and not root.endswith("!")
                                            else "archive-name" if root.endswith("!") else "folder"),
                                 "phrasing": c["phrasing"], "segment": it["segs"][i],
                                 "depth": i}
                chain.append(k)
        full = "\\".join(it["segs"] + [it["fname"]])
        ctx = context_rule(it["drive"], "\\" + full)
        fc = analyse_segment(it["fname"], True, it["segs"], False, rejects,
                             f"{it['drive']}:{full}"[:220], it["drive"], ctx, ancestor_claim=bool(chain))
        for c in fc:
            root = "\\".join(it["segs"])
            k = claim_key(it["drive"], root + "\\<filename>", c["token"])
            if k not in claims:
                claims[k] = {"drive": it["drive"], "claim_root": root, "token": c["token"],
                             "source": "archive-member-filename" if it["is_member"] else "filename",
                             "phrasing": c["phrasing"], "segment": it["fname"],
                             "depth": len(it["segs"])}
            chain.append(k)
        item_chain.append(chain)

    # ---- per item: animal token, researcher ----------------------------------------------------
    def researcher_of(it):
        segs = it["segs"]
        drive = it["drive"]
        flags = []
        who = ""
        top = segs[0] if segs else it["fname"]
        top_clean = top[:-1] if top.endswith("!") else top
        if not segs and it["fname"]:
            top_clean = it["fname"]
        if (drive, top_clean) in ROOT_OWNERS:
            who = ROOT_OWNERS[(drive, top_clean)][0]
        if (drive, top_clean) in TWO_PERSON_ROOTS:
            flags.append(f"two-persons-in-name:{TWO_PERSON_ROOTS[(drive, top_clean)]}")
        level = 0
        persons = []
        for i, s in enumerate(segs):
            s_clean = re.sub(r"(?i)\.(zip|7z|rar)$", "", s[:-1] if s.endswith("!") else s)
            if (drive, tuple(segs[:i])) in PERSON_LEVEL_PARENTS:
                if is_person(s_clean):
                    persons.append((i, s_clean.strip()))
                else:
                    lp = leading_person(s_clean)
                    if lp:
                        persons.append((i, lp))
                        flags.append(f"person-from-mixed-folder-name:{s_clean}")
                    elif not s_clean.startswith("."):
                        flags.append(f"person-level-folder-not-a-person:{s_clean}")
                continue
            if i == 0:
                continue
            if is_person(s_clean):
                persons.append((i, s_clean.strip()))
            else:
                for p in embedded_persons(s_clean):
                    flags.append(f"embedded-person-not-assigned:{p} in '{s_clean}'")
        if not it["is_member"] and (drive, tuple(segs)) in PERSON_LEVEL_PARENTS:
            base = re.sub(r"(?i)\.(zip|7z|rar)$", "", it["fname"])
            if is_person(base):  # e.g. `Former students\Manon.zip`
                persons.append((len(segs), base))
        if it["is_member"] and not persons:
            base = re.sub(r"(?i)\.(zip|7z|rar)$", "", it["relpath"].split("\\")[-1])
            if is_person(base):
                persons.append((0, base))
        if persons:
            who_inner = persons[-1][1]
            if len({p.lower() for _, p in persons} | ({who.lower()} if who else set())) > 1:
                flags.append("nested-person:" + " > ".join(([who] if who else []) + [p for _, p in persons]))
            who = who_inner
        return who, flags

    def animal_of(it):
        cands = animal_tokens(it["fname"])
        src = "filename"
        if not cands:
            for s in reversed(it["segs"]):
                a = [x for x in animal_tokens(s) if x[0] != "lead-number"]
                if len(a) == 1 and not re.search(r"(?i)ID\s*\d+\s*[-–y]\s*\d+", s):
                    cands, src = a, f"folder:{s}"
                    break
                if a:
                    break
        uniq = {c[1] for c in cands}
        if len(uniq) != 1:
            return None, "", ""
        kind, num, raw = cands[0]
        return num, raw, f"{kind}@{src}"

    researcher = []
    animals = []
    r_memo, a_memo = {}, {}
    for it in items:
        rk = (it["drive"], tuple(it["segs"]), it["is_member"], it["relpath"] if it["is_member"] else "",
              it["fname"] if (not it["segs"] or re.search(r"(?i)\.(zip|7z|rar)$", it["fname"])) else "")
        if rk not in r_memo:
            r_memo[rk] = researcher_of(it)
        researcher.append(r_memo[rk])
        ak = (tuple(it["segs"]), it["fname"])
        if ak not in a_memo:
            a_memo[ak] = animal_of(it)
        animals.append(a_memo[ak])
    del r_memo, a_memo

    # ---- resolve each item's nearest claim & conflicts (tokens only; verdicts come later) ---
    nearest = []
    for idx, chain in enumerate(item_chain):
        nearest.append(chain[-1] if chain else None)

    claim_items = collections.defaultdict(list)  # claims -> items whose NEAREST claim it is
    for idx, k in enumerate(nearest):
        if k is not None:
            claim_items[k].append(idx)

    # ---- evaluate a code against a set of items ------------------------------------------------
    def floor_of(P):
        """The earliest date data of this protocol can carry: first animal's birth or the start date."""
        if not P:
            return None
        xs = [x for x in (iso_date(P.get("dob_min")), iso_date(P.get("start_date"))) if x]
        return min(xs) if xs else None

    def evaluate(code, idxs):
        """Cross-check `code` against the files `idxs`. Dates are checked on DATA files only:
        protocol paperwork (CEEA submissions) legitimately predates the first animal."""
        P = db.proto.get(code)
        checked, found, notfound, before_dob = [], [], [], []
        seen = set()
        for i in idxs:
            num, raw, src = animals[i]
            if num is None or num in seen:
                continue
            seen.add(num)
            r = db.lookup(code, num)
            checked.append(num)
            if r["status"] == "found":
                found.append(num)
                d = iso_date(items[i]["date"])
                dob = iso_date(r.get("dob"))
                if d and dob and d < dob and is_data(items[i]["fname"]):
                    before_dob.append(f"{raw}:{items[i]['date']}<dob {r['dob']}")
            else:
                notfound.append(num)
        dates = sorted(d for d in (iso_date(items[i]["date"]) for i in idxs) if d)
        ddates = sorted(d for d in (iso_date(items[i]["date"]) for i in idxs if is_data(items[i]["fname"])) if d)
        dmin, dmax = (dates[0], dates[-1]) if dates else (None, None)
        floor = floor_of(P)
        n_before = sum(1 for d in ddates if floor and d < floor - dt.timedelta(days=31))
        last = max((x for x in (iso_date(P.get("proc_max")), iso_date(P.get("dob_max"))) if x),
                   default=None) if P else None
        n_long_after = sum(1 for d in ddates if last and d > last + dt.timedelta(days=4 * 365))
        return {"P": P, "checked": checked, "found": found, "notfound": notfound,
                "before_dob": before_dob, "dmin": dmin, "dmax": dmax, "floor": floor,
                "n_before": n_before, "n_dates": len(ddates), "last": last,
                "n_long_after": n_long_after}

    def passes(ev, strict):
        """strict (a typo correction): every check clean and >=80% of animals found.
        lenient (the code as written): the bulk agrees; files that individually contradict it
        (their animal is not in the protocol, or they predate it) are demoted file by file."""
        if ev["P"] is None:
            return False
        if strict:
            if not ev["checked"] or not ev["found"]:
                return False
            return (ev["n_before"] == 0 and not ev["before_dob"]
                    and len(ev["found"]) / len(ev["checked"]) >= 0.8)
        if ev["n_dates"] and ev["n_before"] / ev["n_dates"] > 0.2:
            return False
        if ev["checked"]:
            if not ev["found"] or len(ev["found"]) / len(ev["checked"]) < 0.5:
                return False
            if len(ev["before_dob"]) >= 2 and len(ev["before_dob"]) > 0.2 * len(ev["found"]):
                return False
        return True

    def ev_text(code, ev):
        P = ev["P"] or {}
        bits = [f"{code}: valid protocol ({P.get('project_code')})"]
        if ev["checked"]:
            bits.append(f"animals found {len(ev['found'])}/{len(ev['checked'])}"
                        + (f" (found e.g. {','.join(map(str, sorted(ev['found'])[:8]))})" if ev["found"] else "")
                        + (f"; NOT found {','.join(map(str, sorted(ev['notfound'])[:10]))}" if ev["notfound"] else ""))
            cmax = P.get("code_max") or 0
            if ev["checked"] and max(ev["checked"]) <= cmax:
                bits.append(f"weak discrimination: every checked number is <= the protocol's highest animal code "
                            f"{cmax}, so a hit is expected by chance; the dates carry the weight")
            sp = collections.Counter(db.lookup(code, a).get("species") for a in ev["found"])
            if sp:
                bits.append("species " + ", ".join(f"{s} x{n}" for s, n in sp.most_common()))
        else:
            bits.append("no animal numbers in these files")
        bits.append(f"protocol animals DOB {P.get('dob_min')}..{P.get('dob_max')}, n={P.get('n')}, "
                    f"max code {P.get('code_max')}, procedures to {P.get('proc_max')}")
        if ev["dmin"]:
            bits.append(f"file dates {ev['dmin']}..{ev['dmax']}")
        if ev["n_before"]:
            bits.append(f"FAIL {ev['n_before']}/{ev['n_dates']} files dated >31d before the protocol's "
                        f"first animal/start ({ev['floor']})")
        if ev["before_dob"]:
            bits.append("FAIL file dated before that animal's birth: " + "; ".join(ev["before_dob"][:3]))
        if ev["n_long_after"]:
            bits.append(f"note {ev['n_long_after']} files >4y after the protocol's last procedure/birth ({ev['last']})")
        prod = reg_subjects.get(code, set())
        if ev["found"] and prod:
            ov = sorted(set(ev["found"]) & prod)
            bits.append(f"production already has {len(prod)} subjects of {code}; {len(ov)} of the found animals among them")
        return " | ".join(bits)

    # ---- verdict per claim -----------------------------------------------------------------------
    for k, c in claims.items():
        idxs = claim_items.get(k, [])
        c["idxs"] = idxs
        tok = c["token"]
        code = tok if len(tok) == 4 else None
        c["flags"] = []
        if c["claim_root"].startswith("2025-10-02 - Toshiba EXT (Backup)"):
            c["flags"].append("inside-backup-copy")
        if c["claim_root"].startswith("Former students"):
            c["flags"].append("under-Former-students")
        if "!" in c["claim_root"] or c["source"].startswith("archive"):
            c["flags"].append("inside-archive")
        if not idxs:
            c["verdict"] = "SHADOWED"  # every file below has a nearer claim; evaluated there
            c["evidence"] = "no file takes this as its nearest claim (all have a nearer one)"
            c["proposed_project"] = ""
            c["corrected_from"] = ""
            c["ev"] = None
            continue
        if code and code in db.valid:
            ev = evaluate(code, idxs)
            c["ev"] = ev
            if passes(ev, strict=False):
                c["verdict"] = "CONFIRMED"
                c["proposed_project"] = f"AE-biomaGUNE-{code}"
                c["corrected_from"] = ""
                c["evidence"] = ev_text(code, ev) + (
                    "" if ev["checked"] else " | confirmed WITHOUT animal-level evidence (dates only)")
            else:
                c["verdict"] = "C"
                c["proposed_project"] = ""
                c["corrected_from"] = ""
                c["evidence"] = "valid protocol but cross-checks FAIL -> " + ev_text(code, ev)
            continue
        # not a valid code: typo search
        cands = {t: why for t, why in typo_candidates(tok).items() if t in db.valid}
        passing = []
        tried = []
        for t, why in sorted(cands.items()):
            ev = evaluate(t, idxs)
            ok = passes(ev, strict=True)
            tried.append(f"{t} ({why}): animals {len(ev['found'])}/{len(ev['checked'])}"
                         f"{', dates FAIL' if ev['n_before'] or ev['before_dob'] else ''} -> {'PASS' if ok else 'fail'}")
            if ok:
                passing.append((t, why, ev))
        c["typo_tried"] = tried
        if len(passing) == 1:
            t, why, ev = passing[0]
            c["verdict"] = "A"
            c["proposed_project"] = f"AE-biomaGUNE-{t}"
            c["corrected_from"] = f"{tok} -> {t} ({why})"
            c["ev"] = ev
            c["evidence"] = f"'{tok}' is not a protocol; the only passing correction is {t} | " + ev_text(t, ev) \
                            + f" | other candidates: {len(cands) - 1}"
            continue
        c["ev"] = None
        c["corrected_from"] = ""
        why_not = (f"{len(cands)} valid typo candidates, {len(passing)} pass with animal evidence"
                   + (f" ({', '.join(p[0] for p in passing)})" if passing else ""))
        strong = (c["phrasing"].startswith("keyword") or c["phrasing"] in ("folder-exact", "folder-head")
                  or c["phrasing"].startswith("mfb-convention") or c["phrasing"] == "animal-paired")
        # a keyword claim (`Proyecto 0521`) is a project id whatever its digits spell as a date
        dr = [] if c["phrasing"].startswith("keyword") else \
            date_readings(tok, [d for d in (iso_date(items[i]["date"]) for i in idxs) if d])
        if dr:
            why_not += f"; reads as a date close to its files' dates ({', '.join(dr)})"
        if len(tok) == 4 and strong and len(passing) == 0 and not dr:
            c["verdict"] = "B"
            c["proposed_project"] = f"Project-{tok}"
            c["evidence"] = f"'{tok}' is not a protocol in the facility DB; {why_not}; phrased as a project id ({c['phrasing']})"
        else:
            c["verdict"] = "C"
            c["proposed_project"] = ""
            c["evidence"] = f"'{tok}' is not a protocol in the facility DB; {why_not}; phrasing {c['phrasing']}"

    def acq_date(it):
        """Acquisition date: a YYYYMMDD in the file's own name or nearest folder (Bruker study
        names carry it), else the manifest mtime."""
        for s in [it["fname"]] + list(reversed(it["segs"])):  # nearest first; Bruker files sit 4+ below
            m = re.search(r"(?<!\d)((?:19|20)\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])(?!\d)", s)
            if m:
                try:
                    return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))), "name"
                except ValueError:
                    pass
        return iso_date(it["date"]), "mtime"

    def tie_break(codes, num, it):
        """Animal `num` exists in several protocols. Decide only on the facility DB's own dates:
        (1) exactly one protocol logs a procedure on this animal within 3 days of the acquisition;
        else (2) histology only: exactly one protocol's animal had a terminal procedure (organ
        sampling / perfusion) on or before the acquisition date, and rule (3) does not disagree;
        else (3) exactly one protocol's animal was already born by the acquisition date."""
        d, src = acq_date(it)
        if not d:
            return None, "no acquisition date"
        near, alive, terminal = [], [], []
        for code in codes:
            r = db.lookup(code, num)
            procs = [iso_date(p[0]) for p in r.get("procs", [])]
            if any(p and abs((p - d).days) <= 3 for p in procs):
                near.append(code)
            if any(t and t.year >= 1990 and t <= d and TERMINAL_PROC_RE.search(ty or "")
                   for t, ty in ((iso_date(p[0]), p[1]) for p in r.get("procs", []))):
                terminal.append(code)
            dob = iso_date(r.get("dob"))
            if dob and dob <= d:
                alive.append(code)
        if len(near) == 1:
            return near[0], f"decided {near[0]}: only it logs a procedure on animal {num} within 3 days of {d} ({src} date)"
        ext = it["fname"].rsplit(".", 1)[-1].lower() if "." in it["fname"] else ""
        if ext in HISTOLOGY_EXT and len(terminal) == 1:
            if terminal[0] != codes[0]:
                # The DB logs sampling unevenly (1321's animals 98-101 have slides on the drive but
                # no sampling logged), so a MISSING terminal procedure is not evidence. The rule may
                # confirm the file's own nearest claim; it never overrules it.
                return None, (f"terminal procedure only on the outer {terminal[0]}'s animal {num} by {d} "
                              f"({src}); the rule never overrules the nearest claim {codes[0]}")
            if len(alive) == 1 and alive[0] != terminal[0]:
                return None, (f"terminal procedure on {terminal[0]} but only {alive[0]}'s animal {num} "
                              f"was born by {d} ({src}) -- the rules disagree")
            return terminal[0], (f"decided {terminal[0]}: only its animal {num} had organ sampling/perfusion "
                                 f"on or before {d} ({src} date; histology)")
        if len(alive) == 1:
            return alive[0], f"decided {alive[0]}: only its animal {num} was born by {d} ({src} date)"
        return None, (f"procedure-date match {near or 'none'}, terminal-by-date {terminal or 'none'}, "
                      f"born-by-date {alive or 'none'} on {d} ({src})")

    # ---- per item final decision (conflicts) -----------------------------------------------------
    item_decision = []
    conflicts = collections.Counter()
    for idx, chain in enumerate(item_chain):
        if not chain:
            item_decision.append((None, "", "", ""))
            continue
        k = chain[-1]
        c = claims[k]
        others = [claims[x] for x in chain[:-1]]
        outer_tokens = sorted({o["token"] for o in others if o["token"] != c["token"]})
        conflict = ""
        verdict, proj = c["verdict"], c["proposed_project"]
        if outer_tokens:
            conflict = f"nested claims disagree: nearest {c['token']} ({c['verdict']}) vs outer {','.join(outer_tokens)}"
            num = animals[idx][0]
            if verdict in ("CONFIRMED", "A") and num is not None:
                code = proj[-4:]
                r_in = db.lookup(code, num)["status"]
                outs = {o["token"]: db.lookup(o["token"], num)["status"] for o in others
                        if o["token"] in db.valid and o["token"] != c["token"]}
                also = [t for t, s in outs.items() if s == "found"]
                if r_in == "found" and not also:
                    conflict += f"; decided for nearest: animal {num} found in {code}, not in " + \
                        (",".join(outs) or "the outer (not a protocol)")
                elif r_in == "found":
                    win, why = tie_break([code] + also, num, items[idx])
                    if win:
                        conflict += f"; animal {num} is in both {code} and {','.join(also)}; {why}"
                        if win != code:
                            conflict += f" (the OUTER claim {win} wins; claim_id still names the nearest)"
                        verdict, proj = "CONFIRMED", f"AE-biomaGUNE-{win}"
                    else:
                        conflict += f"; animal {num} is found in BOTH {code} and {','.join(also)}, " \
                                    f"and the DB dates do not separate them ({why}) -> C (ambiguous)"
                        verdict, proj = "C", ""
                else:
                    conflict += f"; animal {num} NOT found in nearest {code} -> C"
                    verdict, proj = "C", ""
            elif verdict in ("CONFIRMED", "A"):
                conflict += "; no animal number to decide between them -> C"
                verdict, proj = "C", ""
            else:
                conflict += "; nearest is unresolved -> C"
                verdict, proj = "C", ""
            conflicts[(c["drive"], c["claim_root"], c["token"], ",".join(outer_tokens), verdict)] += 1
        # file-level cross-check: a file whose OWN animal or date contradicts the protocol is demoted
        if verdict in ("CONFIRMED", "A"):
            code = proj[-4:]
            it = items[idx]
            num, raw, src = animals[idx]
            d = iso_date(it["date"])
            if num is not None:
                r = db.lookup(code, num)
                if r["status"] != "found":
                    verdict, proj = "C", ""
                    conflict = (conflict + "; " if conflict else "") + \
                        f"file's animal {raw} is not in protocol {code} -> C"
                elif d and is_data(it["fname"]) and iso_date(r.get("dob")) and d < iso_date(r["dob"]):
                    verdict, proj = "C", ""
                    conflict = (conflict + "; " if conflict else "") + \
                        f"file dated {it['date']} before animal {num} of {code} was born ({r['dob']}) -> C"
            if verdict != "C" and d and is_data(it["fname"]):
                fl = floor_of(db.proto.get(code))
                if fl and d < fl - dt.timedelta(days=31):
                    verdict, proj = "C", ""
                    conflict = (conflict + "; " if conflict else "") + \
                        f"data file dated {it['date']} predates protocol {code} (first animal/start {fl}) -> C"
        item_decision.append((k, verdict, proj, conflict))

    # ---- subject ids -----------------------------------------------------------------------------
    subject = []
    for idx, (k, verdict, proj, conflict) in enumerate(item_decision):
        num, raw, src = animals[idx]
        sid = ""
        if verdict in ("CONFIRMED", "A") and num is not None and src.split("@")[0] in ("ID", "m"):
            r = db.lookup(proj[-4:], num)
            if r["status"] == "found":
                try:
                    sid = animal_db.compose_subject_id(num, proj[-4:])
                except ValueError as e:
                    errors[f"compose_subject_id refused: {e}"] += 1
        subject.append(sid)
    db.save()

    # ---- write outputs ---------------------------------------------------------------------------
    manifest_idx = [i for i, it in enumerate(items) if not it["is_member"]]
    member_idx_by_archive = collections.defaultdict(list)
    for i, it in enumerate(items):
        if it["is_member"]:
            member_idx_by_archive[(it["drive"], it["relpath"])].append(i)

    # claim ids, stable order
    order = sorted((k for k in claims if claims[k]["verdict"] != "SHADOWED"),
                   key=lambda k: (k[0], k[1], k[2]))
    shadowed = sorted(k for k in claims if claims[k]["verdict"] == "SHADOWED")
    cid = {}
    for n, k in enumerate(order + shadowed, 1):
        cid[k] = f"CL-{n:04d}"

    # per-claim aggregates use the FINAL per-item decision
    agg = collections.defaultdict(lambda: {"n": 0, "czi": 0, "bytes": 0, "dates": [], "res": collections.Counter(),
                                           "final": collections.Counter()})
    for idx, (k, verdict, proj, conflict) in enumerate(item_decision):
        if k is None:
            continue
        a = agg[k]
        it = items[idx]
        a["n"] += 1
        a["czi"] += it["fname"].lower().endswith(".czi")
        a["bytes"] += it["size"]
        if it["date"]:
            a["dates"].append(it["date"])
        if researcher[idx][0]:
            a["res"][researcher[idx][0]] += 1
        a["final"][verdict] += 1
        for f in researcher[idx][1]:
            if f.startswith("nested-person") or f.startswith("person-from-mixed") or f.startswith("two-persons"):
                claims[k]["flags"].append(f)

    claim_cols = ["claim_id", "drive", "claim_root", "token", "source", "verdict", "proposed_project",
                  "project_status", "corrected_from", "evidence", "n_files", "n_czi", "bytes", "date_min",
                  "date_max", "researchers", "animals_checked", "animals_found", "flags", "phrasing", "segment"]
    with open(os.path.join(args.out, "claims.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(claim_cols)
        for k in order + shadowed:
            c = claims[k]
            a = agg[k]
            ev = c.get("ev") or {}
            pstat = ""
            if c["proposed_project"]:
                pstat = reg_projects.get(c["proposed_project"].lower(), "NEW")
            flags = list(dict.fromkeys(c["flags"]))
            if a["final"] and set(a["final"]) != {c["verdict"]}:
                flags.append("per-file-overrides:" + ",".join(f"{v}={n}" for v, n in sorted(a["final"].items())))
            if c.get("typo_tried"):
                flags.append("typo-candidates: " + " ; ".join(c["typo_tried"][:12]))
            w.writerow([cid[k], c["drive"], c["claim_root"], c["token"], c["source"], c["verdict"],
                        c["proposed_project"], pstat, c["corrected_from"], c["evidence"], a["n"], a["czi"],
                        a["bytes"], min(a["dates"]) if a["dates"] else "", max(a["dates"]) if a["dates"] else "",
                        "; ".join(f"{r} ({n})" for r, n in a["res"].most_common()),
                        len(ev.get("checked", [])), len(ev.get("found", [])),
                        " | ".join(flags[:20]), c["phrasing"], c["segment"]])

    fc_cols = ["drive", "relpath", "claim_id", "verdict", "proposed_project", "researcher", "animal_token",
               "subject_id", "conflict"]
    counts = collections.Counter()
    with open(os.path.join(args.out, "file_claims.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(fc_cols)
        for idx in manifest_idx:
            it = items[idx]
            k, verdict, proj, conflict = item_decision[idx]
            key = (it["drive"], it["relpath"])
            if key in member_idx_by_archive and not k:
                mems = member_idx_by_archive[key]
                projs = collections.Counter(item_decision[m][2] or f"<{item_decision[m][1] or 'none'}>" for m in mems)
                claimed = {p for p in projs if not p.startswith("<none")}
                if claimed:
                    conflict = ("archive members carry claims: " +
                                "; ".join(f"{p} x{n}" for p, n in projs.most_common(8)) +
                                " -- see archive_member_claims.csv")
                    verdict = "ARCHIVE"
            who, rflags = researcher[idx]
            num, raw, src = animals[idx]
            counts[verdict or "NO-CLAIM"] += 1
            w.writerow([it["drive"], it["relpath"], cid.get(k, ""), verdict, proj, who, raw,
                        subject[idx], conflict])

    # no-claim files grouped by (researcher, series) -- the default Ryan is asked to confirm:
    # blank project, listed for a human to map. Series = first folder below the researcher's folder
    # (two levels inside the Toshiba backup, whose owner is implied rather than a folder).
    groups = collections.defaultdict(lambda: [0, 0, 0, [], ""])
    for idx in manifest_idx:
        it = items[idx]
        if item_decision[idx][0] or (it["drive"], it["relpath"]) in member_idx_by_archive and \
                any(item_decision[m][0] for m in member_idx_by_archive[(it["drive"], it["relpath"])]):
            continue
        parts = it["relpath"].split("\\")
        who = researcher[idx][0]
        pos = None
        for i, p in enumerate(parts[:-1]):
            if who and (p.lower() == who.lower() or p.lower().startswith(who.lower())):
                pos = i
        if pos is not None:
            series = parts[pos + 1] if pos + 1 < len(parts) - 1 else "(loose files in the person folder)"
        elif parts[0].startswith("2025-10-02"):
            series = "\\".join(parts[1:3]) if len(parts) > 3 else parts[1] if len(parts) > 2 else "(backup root)"
        else:
            series = "\\".join(parts[:2]) if len(parts) > 2 else parts[0] if len(parts) > 1 else "(drive root)"
        g = groups[(it["drive"], who, series)]
        g[0] += 1
        g[1] += it["fname"].lower().endswith(".czi")
        g[2] += it["size"]
        if it["date"]:
            g[3].append(it["date"])
        g[4] = g[4] or it["relpath"]
    with open(os.path.join(args.out, "noclaim_groups.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["drive", "researcher", "series", "n_files", "n_czi", "bytes", "date_min", "date_max", "example"])
        for (d, who, series), g in sorted(groups.items(), key=lambda kv: -kv[1][2]):
            w.writerow([d, who, series, g[0], g[1], g[2], min(g[3]) if g[3] else "", max(g[3]) if g[3] else "", g[4]])

    with open(os.path.join(args.out, "archive_member_claims.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["drive", "archive_relpath", "member", "claim_id", "verdict", "proposed_project",
                    "researcher", "animal_token", "subject_id", "conflict", "size", "member_date"])
        for (drive, rp), mems in sorted(member_idx_by_archive.items()):
            if not any(item_decision[m][0] for m in mems):
                continue
            for m in mems:
                k, verdict, proj, conflict = item_decision[m]
                it = items[m]
                w.writerow([drive, rp, it["member"], cid.get(k, ""), verdict, proj, researcher[m][0],
                            animals[m][1], subject[m], conflict, it["size"], it["date"]])

    with open(os.path.join(args.out, "rejected_tokens.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["token", "reason", "source", "occurrences", "example"])
        for (tok, reason, source), (n, ex) in sorted(rejects.d.items(), key=lambda kv: (kv[0][1], -kv[1][0], kv[0][0])):
            w.writerow([tok, reason, source, n, ex])

    # safety net: rejected pure-number tokens whose value (or zero-padded value) is a valid code
    with open(os.path.join(args.out, "safety_net.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["token", "as_code", "reason", "source", "occurrences", "example"])
        for (tok, reason, source), (n, ex) in sorted(rejects.d.items()):
            if re.fullmatch(r"\d{4}", tok) or (re.fullmatch(r"\d{3}", tok) and source == "folder"):
                code = tok.zfill(4)
                if code in db.valid and not reason.startswith(("short-number", "fluorophore")):
                    w.writerow([tok, code, reason, source, n, ex])

    with open(os.path.join(args.out, "run_summary.txt"), "w", encoding="utf-8") as f:
        f.write(f"run {dt.datetime.now().isoformat(timespec='seconds')}\n")
        # every drive the run was given (drives 1+2 print as before: "(drive1 N, drive2 M)"; a wrapper for a
        # third drive no longer has to fake empty drive1/drive2 manifests for this line)
        f.write(f"manifest files: {n_manifest} ("
                + ", ".join(f"{d} {len(m)}" for d, m in manifests.items()) + ")\n")
        f.write(f"archive members listed: {len(items) - n_manifest}\n")
        f.write(f"valid protocol codes in DB: {len(db.valid)}\n")
        f.write(f"DB lookups this run (uncached): {db.lookups}\n")
        f.write(f"claims: {len(order)} active, {len(shadowed)} shadowed\n")
        f.write("claims by verdict: " + json.dumps(collections.Counter(claims[k]["verdict"] for k in order)) + "\n")
        f.write("file_claims verdicts: " + json.dumps(counts) + "\n")
        f.write(f"conflict groups: {len(conflicts)}\n")
        for (d, root, t, outer, v), n in sorted(conflicts.items()):
            f.write(f"  conflict {d} {root} nearest={t} outer={outer} -> {v} items={n}\n")
        f.write(f"errors/notes: {sum(errors.values())}\n")
        for e, n in errors.most_common():
            f.write(f"  {n} x {e}\n")
    print(open(os.path.join(args.out, "run_summary.txt"), encoding="utf-8").read())


if __name__ == "__main__":
    main()
