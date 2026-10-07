#!/usr/bin/env python3
"""p_plan.py -- stream P: the M. Jesus drive's (drive 3) non-raw placement, as a nonraw_placement manifest.

Part A2 planned the placement (tasks/drive3_projects_and_placement.md; its placement_plan.csv on D:). This
turns that plan into the manifest that `nonraw_placement.py copy / verify / holding` run on: the
coordinator's calls of 2026-10-06 applied, A2's dedup re-run over the result, every destination planned
again with the shared rule (historical_paths.py, through nonraw_placement.assign_destinations) against the
LIVE NAS, and the invariants checked. Record: tasks/drive3_placement_gate.md.

    set PYTHONDONTWRITEBYTECODE=1
    python tools/drive_staging/drive3/p_plan.py plan     [--out DIR]
    python tools/drive_staging/drive3/p_plan.py release  --manifest M --hold TAG [--project NAME] --out DIR
    python tools/drive_staging/drive3/p_plan.py handover --manifest M [--manifest M2 ...] --csv LIST --stream X --out DIR
                                                         [--hold TAG] [--raw-index CSV]

READ-ONLY on J: (production and the staged copy alike). Writes only under --out. /raw/ is always read live
(every acquisition's checksums.json, p_verify.live_raw_index), never from a dated analysis index.

THE CALLS (HANDOFF §1 of feat/drive3-placement; tasks/drive3_production_plan.md, "Rules every stream follows")
  C1  AE-biomaGUNE-1121 was reopened on 2026-10-06: A2's `place-after-reopen` -> place.
  C2  Protocol 0118 waits on STATUS §0.5 M1. What A2 planned under Ryan's 09-30 names
      (Proyecto-0118-rats-hipoxia / -Monocrotalina) is planned under AE-biomaGUNE-0118 (answer U). The
      Monocrotalina documents (Pili y Mili\\Proyecto 0118 Monocrotalina), which land there under either
      answer, are placed now; the rest is HELD (hold M1-0118). Answer E changes only the base folder.
  C3  AE-biomaGUNE-1521 and -0618 are closed, and their reopen waits on Ryan's go: HELD
      (hold reopen-<project>).
  C4  A2 D5: the 25 files drives 1+2 placed under another project are ALSO placed in drive 3's project.
  C5  The model outputs (A3 S6) go to the holding folder, beside the group's tool (A2 D8): every file in a
      `Predict_Slicer` folder (Vicomtech predictions) and the Pred_ / Postprocessed_ / Modificated_
      volumes of Otros\\Segmentaciones ITK SNAP\\Segmentacion 2DG RATAS (the 2019 rat predictions).
  P1  (this stream's own, following the drives 1+2 precedent) the one .zip A2 placed whole is expanded,
      as every drives 1+2 archive was (Ryan, 2026-10-02: no zips): its 2 members are placed, not the zip.
  N1  (coordinator, 2026-10-06, found by stream N) the 49 PMOD DICOM exports (A1 pet_files.csv, kind
      pmod-export: SUV-scaled and co-registered volumes) are derivatives no stream planned. A2 left them to A1
      because they are DICOM by content; they join A2's rows here, decided by A2's own rules (pmod_rows).
  A2's readings R1-R4, its "one study folder per content" dedup (D3) and D8 stand as A2 applied them.

DECISIONS IN THE MANIFEST: place (copied in the project windows), holding (copied in the holding window),
held (planned, never copied until `release`), and, listed only: already-placed, already-in-holding,
duplicate-copy, covered-by-twin, deferred (biomaGUNE MJ), exclude (zero-byte), expanded (the zip).
"""
import argparse
import collections
import csv
import datetime as dt
import hashlib
import io
import json
import os
import re
import shutil
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))       # tools/drive_staging/drive3
DS = os.path.dirname(HERE)                              # tools/drive_staging
TOOLS = os.path.dirname(DS)                             # tools
REPO = os.path.dirname(TOOLS)
for _p in (TOOLS, DS, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import historical_paths as H  # noqa: E402  (THE destination rule)
import nonraw_placement as NP  # noqa: E402  (the copy tool: manifest format, assign_destinations)
from catalog import file_ext  # noqa: E402

ANALYSIS = r"D:\projects\gjesus3\drive3_analysis"
A2_PLAN = os.path.join(ANALYSIS, "a2", "placement", "placement_plan.csv")
A2_FILES = os.path.join(ANALYSIS, "a2", "files.csv")
A2_CLAIMS = os.path.join(ANALYSIS, "a2", "claims")
A3_LABELS = os.path.join(ANALYSIS, "a3", "a3_labels_final.csv")
MANIFEST_COPY = os.path.join(ANALYSIS, "drive3_manifest.csv")
DRIVE = "D3"
LABEL, STAGED = NP.DRIVES[DRIVE]
TAG = H.TAGS[DRIVE]
MANIFEST_NAS = os.path.join(STAGED, "manifest.csv")
VERIFY_PROBLEMS = os.path.join(STAGED, "verify_problems.csv")
OUT_DEFAULT = r"D:\projects\gjesus3\drive3_streams\placement\manifest"

P0118 = "AE-biomaGUNE-0118"
P0118_E = "Proyecto-0118-rats-hipoxia"                    # M1's fallback answer E: a new project
A2_0118_NAMES = ("Proyecto-0118-rats-hipoxia", "Proyecto-0118-Monocrotalina")   # A2 used Ryan's 09-30 names
MONO_PREFIX = "Pili y Mili\\Proyecto 0118 Monocrotalina\\"
HOLD_M1 = "M1-0118"
HELD_SEP = " | HELD: "                                    # reason = <why placed> | HELD: <what it waits on>
TOP_ORDER = ["Pili y Mili", "MRI", "PET", "Otros", "Microscopio", "biomaGUNE MJ"]   # A2's canonical-copy order
RAT_2DG = "Otros\\Segmentaciones ITK SNAP\\Segmentacion 2DG RATAS\\"
RAT_2DG_PRED = ("Pred_", "Postprocessed_", "Modificated_")
D8_PREFIX = "Otros\\PH_analysis_Segmentation_tool\\"
A2_FINAL = {"deferred-biomaGUNE-MJ": "deferred", "exclude-zero-byte": "exclude", "in-raw": "in-raw",
            "already-placed": "already-placed", "already-in-holding": "already-in-holding",
            "holding-nmr": "holding"}
LISTED_ONLY = ("already-placed", "already-in-holding", "duplicate-copy", "covered-by-twin", "deferred",
               "exclude", "expanded", "in-raw")


# ------------------------------------------------------------------------------------------- io

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
        w.writerows(rows)


def gb(n):
    return f"{n / 1e9:.2f}"


def sha256_path(path, bufsize=8 << 20):
    h = hashlib.sha256()
    with open(NP.lp(path), "rb") as f:
        while True:
            b = f.read(bufsize)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def stdout_utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="backslashreplace")
        except AttributeError:
            pass


# --------------------------------------------------------------------------------- the rules

def model_output(relpath):
    """C5: is this one of A3 S6's model outputs? -> the reason, or ''."""
    parts = relpath.split("\\")
    if any(p.lower() == "predict_slicer" for p in parts[:-1]):
        return "C5 model output (A3 S6): a Vicomtech prediction (Predict_Slicer), kept with the tool"
    if relpath.startswith(RAT_2DG) and parts[-1].startswith(RAT_2DG_PRED):
        return "C5 model output (A3 S6): a 2019 rat model prediction (Segmentacion 2DG RATAS), kept with the tool"
    return ""


def a2_pre(a):
    """A2's decision BEFORE its content-level step and its dedup, recovered from its final one: a row A2
    would place (`candidate`), a row with no project (`unattributed`), or a final decision."""
    d = a["dec_rec"]
    if d in ("place", "place-after-reopen", "closed-project"):
        return "candidate"
    if d in ("covered-by-twin", "holding"):
        return "unattributed"
    if d == "duplicate-copy":
        return "candidate" if a["rec_project"] else "unattributed"
    return d   # deferred-biomaGUNE-MJ, exclude-zero-byte, in-raw, already-placed, already-in-holding, placed-elsewhere


def target(a2_project, relpath, projects):
    """(project, decision, hold, call) for a row A2 would place in `a2_project`, by the calls."""
    if a2_project in A2_0118_NAMES:                                    # C2
        if relpath.startswith(MONO_PREFIX):
            return P0118, "place", "", "C2: the 0118 Monocrotalina documents land in AE-biomaGUNE-0118 under either M1 answer"
        return P0118, "held", HOLD_M1, "C2: protocol 0118 waits on STATUS §0.5 M1 (U: AE-biomaGUNE-0118; E: Proyecto-0118-rats-hipoxia)"
    row = projects.get(a2_project)
    if row is None:
        raise SystemExit(f"STOP: {a2_project} is not in the live registry (A2 planned files for it)")
    st = (row.get("status") or "").strip().lower()
    if st == "closed":                                                # C3
        return a2_project, "held", f"reopen-{a2_project}", \
            f"C3: {a2_project} is closed; its reopen waits on Ryan's go (05 §4.y)"
    if st != "active":
        raise SystemExit(f"STOP: {a2_project} has status {st!r}")
    return a2_project, "place", "", ""


def canon_order(w):
    """A2's canonical copy (a2_placement.order_for): the OUTERMOST study folder first, then the shared
    group folders before biomaGUNE MJ, then the shallower path, then the name."""
    rk = w["root"]
    depth = len(rk.split("|")) if rk and rk != "-" else 99
    top = TOP_ORDER.index(w["top"]) if w["top"] in TOP_ORDER else 9
    path = w["relpath"] + ("!" + w["member"] if w["member"] else "")
    return (depth, top, path.count("\\"), path.lower())


def content_and_dedup(work):
    """A2's last two steps, re-run over the decided rows (in place):
    1. content level: a row with no project whose exact bytes go to a project through another copy
       (place / held / already-placed) is `covered-by-twin`; otherwise `holding`;
    2. dedup, one study folder per content (A2 D3): copies of the same bytes bound for one project (or the
       holding folder) are kept only under the canonical copy's study folder; the others are
       `duplicate-copy`. The holding folder has no study folder, so every copy there is kept."""
    covering = {}
    for w in work:
        if w["decision"] in ("place", "held", "already-placed"):
            covering.setdefault(w["sha256"], w)
    for w in work:
        if w["decision"] == "unattributed":
            tw = covering.get(w["sha256"])
            if tw is not None:
                w["decision"] = "covered-by-twin"
                w["note"] = f"twin {tw['decision']} in {tw['project'] or '?'}: {tw['relpath']}"
            else:
                w["decision"] = "holding"
    groups = collections.defaultdict(list)
    for w in work:
        if w["decision"] in ("place", "held", "holding"):
            groups[(w["project"] or "(holding)", w["sha256"])].append(w)
    for fs in groups.values():
        fs.sort(key=canon_order)
        best = fs[0]["root"]
        for x in fs[1:]:
            if x["root"] != best:
                x["held_was"] = x["hold"]
                x["decision"], x["hold"] = "duplicate-copy", ""
                x["note"] = (f"canonical ({fs[0]['decision']}): {fs[0]['relpath']}"
                             + (f"!{fs[0]['member']}" if fs[0]["member"] else ""))
    return work


def decide(a2rows, projects, root_of, zip_members=None):
    """A2's rows -> work rows with this stream's decisions (calls C1-C5, P1), then A2's content-level step
    and dedup. `root_of(relpath, project)` gives a study folder for a C4 row (A2 never computed one);
    `zip_members`: {zip relpath: [(member, size, sha256)]} for P1."""
    work = []
    for a in a2rows:
        w = {"relpath": a["relpath"], "archive": "", "member": "", "size": int(a["size"]), "sha256": a["sha256"],
             "cls": a["cls"], "top": a["top"], "claim_id": a["claim_id"],
             "verdict": "" if a["verdict"] == "NO-CLAIM" else a["verdict"], "reading": a["reading"],
             "a2_dec": a["dec_rec"], "a2_project": a["rec_project"], "a2_dest": a["dest"],
             "root": a["root_rec"] or "", "project": "", "decision": "", "hold": "", "call": "", "note": "",
             "held_was": "", "n1": a.get("n1", "")}
        pre = a2_pre(a)
        mo = model_output(a["relpath"]) if pre in ("candidate", "unattributed") else ""
        if mo:                                                         # C5
            w.update(decision="holding", root="", call=mo)
            work.append(w)
            continue
        if pre == "candidate":
            proj, dec, hold, call = target(a["rec_project"], a["relpath"], projects)
            if a["dec_rec"] == "place-after-reopen":
                call = "C1: AE-biomaGUNE-1121 reopened 2026-10-06"
            if a["cls"] == "archive" and zip_members is not None and a["relpath"] in zip_members:   # P1
                w.update(project=proj, decision="expanded",
                         call="P1: an archive is expanded (Ryan 2026-10-02: no zips); its members are placed")
                work.append(w)
                for member, size, sha in zip_members[a["relpath"]]:
                    m = dict(w, archive=a["relpath"], member=member, size=int(size), sha256=sha,
                             cls=NP_class(member), decision=dec, hold=hold,
                             call="P1: member of an expanded archive" + (f"; {call}" if call else ""), note="")
                    work.append(m)
                continue
            w.update(project=proj, decision=dec, hold=hold, call=call)
        elif pre == "placed-elsewhere":                                # C4
            proj, dec, hold, call = target(a["rec_project"], a["relpath"], projects)
            root = root_of(a["relpath"], proj)
            if not root:
                raise SystemExit(f"STOP: no study folder for the C4 row {a['relpath']} in {proj}")
            w.update(project=proj, decision=dec, hold=hold, root=root,
                     call=("C4 (A2 D5): also placed in drive 3's project" + (f"; {call}" if call else "")),
                     note=f"same bytes placed by drives 1+2 in {a['placed12']}")
        elif pre == "unattributed":
            w["decision"] = "unattributed"
        elif pre in A2_FINAL:
            w["decision"] = A2_FINAL[pre]
            if pre == "already-placed":   # A2's 0118 working names: the 19 sit in AE-biomaGUNE-0118 (drive 1)
                w["project"] = P0118 if a["rec_project"] in A2_0118_NAMES else a["rec_project"]
            if pre == "already-placed":
                w["note"] = f"placed by drives 1+2 in {a['placed12']}"
            elif pre == "already-in-holding":
                w["note"] = "in the drives 1+2 holding folder"
            elif pre == "exclude-zero-byte":
                w["note"] = "zero-byte: counted, not placed"
        else:
            raise SystemExit(f"STOP: unknown A2 decision {a['dec_rec']!r} for {a['relpath']}")
        if w["n1"]:                                                    # N1: stream N's PMOD exports
            n1 = "N1: a PMOD DICOM export (stream N), non-raw by A2's rules"
            w["call"] = f"{n1}; {w['call']}" if w["call"] else n1
        work.append(w)
    return content_and_dedup(work)


def NP_class(name):
    """The class of an archive member (A2's classes, by extension)."""
    ext = file_ext(name)
    if ext in (".doc", ".docx", ".pdf", ".xlsx", ".xls", ".pptx", ".ppt", ".txt", ".csv", ".odt"):
        return "document"
    return "other"


def reason_of(w):
    """The manifest's `reason`: why the row lands where it does (provenance carries it)."""
    if w["decision"] == "holding":
        if w["call"]:
            return w["call"]
        if w["relpath"].startswith(D8_PREFIX):
            return "A2 D8: the group's own 3D Slicer tool and trained models (not project data)"
        return "(C) claim" if w["verdict"] == "C" else ("no claim" if not w["verdict"] else f"verdict {w['verdict']}")
    base = f"claim {w['verdict'] or 'none'}"
    if w["reading"]:
        base += f"; reading {w['reading']} (A2 D2, accepted)"
    if w["decision"] == "held":
        return base + HELD_SEP + w["call"]
    return base + (f"; {w['call']}" if w["call"] else "")


# ------------------------------------------------------------------------------------- inputs

def load_projects(nas):
    return NP.load_projects(nas)


def verify_drive_manifest(say):
    """The drive manifest is the authority: the D: copy A2 used must be byte-identical to the staged one."""
    a, b = sha256_path(MANIFEST_COPY), sha256_path(MANIFEST_NAS)
    say(f"drive manifest: D: copy {a[:16]}..  staged {b[:16]}..  {'IDENTICAL' if a == b else 'DIFFERENT'}")
    if a != b:
        raise SystemExit("STOP: the D: copy of the drive manifest differs from the staged one")
    out = {}
    for r in it(MANIFEST_COPY):
        out[r["relpath"]] = (int(r["size"] or 0), r["sha256"])
    return out, a


def zip_members_of(a2rows, manifest, say):
    """P1: list and hash every member of each .zip A2 would place, read once from the staged copy, after
    the zip's own bytes are checked against the drive manifest."""
    out = {}
    for a in a2rows:
        if a["cls"] != "archive" or a_pre_is_candidate(a) is False:
            continue
        path = os.path.join(STAGED, "files", a["relpath"])
        sha = sha256_path(path)
        if (int(a["size"]), sha) != manifest[a["relpath"]]:
            raise SystemExit(f"STOP: staged zip differs from the drive manifest: {a['relpath']}")
        mem = []
        with zipfile.ZipFile(NP.lp(path)) as z:
            for zi in z.infolist():
                if zi.is_dir():
                    continue
                h = hashlib.sha256()
                with z.open(zi) as f:            # zipfile checks each member's CRC at EOF
                    for b in iter(lambda: f.read(1 << 20), b""):
                        h.update(b)
                mem.append((zi.filename, zi.file_size, h.hexdigest()))
        out[a["relpath"]] = mem
        say(f"P1 zip expanded: {a['relpath']} ({len(mem)} members, zip sha256 = drive manifest)")
    return out


def a_pre_is_candidate(a):
    return a2_pre(a) == "candidate"


def claim_roots():
    """A2's claim roots (a2_placement.build_claim_roots, unchanged) and its root rule (root_for)."""
    import a2_placement as A2P
    projects = NP.load_projects(NP.NAS_DEFAULT)
    claims = list(it(os.path.join(A2_CLAIMS, "claims.csv")))
    roots, fn_roots, _n = A2P.build_claim_roots(claims, projects)

    def root_of(relpath, project):
        r = A2P.root_for(relpath, project, roots, fn_roots)
        return "|".join(r) if r else ""
    return root_of


def researchers(relpaths):
    want = set(relpaths)
    out = {}
    for r in it(os.path.join(A2_CLAIMS, "file_claims.csv")):
        if r["relpath"] in want and r.get("researcher"):
            out[r["relpath"]] = r["researcher"]
    return out


# ------------------------------------------------------------- non-raw files A2 did not own (N1)

PET_FILES = os.path.join(ANALYSIS, "a1", "pet_files.csv")
PMOD_CLASS = "pmod-dicom"     # DICOM by its DICM preamble (Manufacturer PMOD): a derived volume, not raw


def pmod_rows(projects, raw_shas, root_of, say):
    """N1 (coordinator, 2026-10-06, from stream N): the PMOD DICOM exports (SUV-scaled and co-registered
    volumes, Manufacturer PMOD; A1 pet_files.csv kind = pmod-export) are derivatives that no stream planned.
    They are DICOM by content, so A2 left them to A1; they are placed as non-raw by A2's OWN rules, as rows
    in A2's plan format: the engine's claim, A2's readings, A2's first decision (biomaGUNE MJ deferred;
    already in /raw/ -- read live; already placed or held by drives 1+2), and A2's study folder. decide()
    then applies the calls and the dedup to them with every other row. -> rows like placement_plan.csv's."""
    import a2_placement as A2P
    import project_claims as PC
    want = {r["relpath"] for r in it(PET_FILES) if r.get("kind") == "pmod-export"}
    files = {r["relpath"]: r for r in it(A2_FILES) if r["relpath"] in want}
    fcl = {r["relpath"]: r for r in it(os.path.join(A2_CLAIMS, "file_claims.csv")) if r["relpath"] in want}
    cl_by_id = {c["claim_id"]: c for c in it(os.path.join(A2_CLAIMS, "claims.csv"))}
    with open(os.path.join(A2_CLAIMS, "db_cache.json"), encoding="utf-8") as fh:
        cache = json.load(fh)
    if set(files) != want:
        raise SystemExit(f"STOP: {len(want - set(files))} PMOD exports are not in A2's files.csv")
    out = []
    for rel in sorted(want):
        f = dict(files[rel])
        f["animal_token"] = fcl.get(rel, {}).get("animal_token", "")
        f["proposed_project"] = fcl.get(rel, {}).get("proposed_project", f.get("proposed_project", ""))
        ep = A2P.engine_project(f)
        reading, rp = "", ""
        if not ep:                                   # A2's readings R1-R3 (R4 are folder prefixes, below)
            c = cl_by_id.get(f["claim_id"])
            m = re.match(r"nested claims disagree: nearest (\d{4}) \(C\) vs outer (\d{4}); nearest is unresolved",
                         f["conflict"])
            if f["claim_id"] == "CL-1344" and not A2P.contradicted_0522(f, cache, PC.is_data):
                reading, rp = "R1", "AE-biomaGUNE-0522"
            elif f["claim_id"] == "CL-0772":
                reading, rp = "R2", "AE-biomaGUNE-1019"
            elif m and c and A2P.DATE_TOKEN_EVIDENCE in c["evidence"] and f"AE-biomaGUNE-{m.group(2)}" in projects:
                reading, rp = "R3", f"AE-biomaGUNE-{m.group(2)}"
            for rid, (prefix, proj) in A2P.NO_CODE_ROOTS.items():
                if not reading and rel.startswith(prefix + "\\"):
                    reading, rp = rid, proj
        proj = ep or rp
        if proj == P0118:
            proj = "Proyecto-0118-Monocrotalina" if rel.startswith(MONO_PREFIX) else "Proyecto-0118-rats-hipoxia"
        placed = set(f["placed12"].split(";")) - {""}
        folder = (P0118 if proj in A2_0118_NAMES else proj)
        if f["top"] == "biomaGUNE MJ":
            dec = "deferred-biomaGUNE-MJ"
        elif int(f["size"]) == 0:
            dec = "exclude-zero-byte"
        elif f["sha256"] in raw_shas:
            dec = "in-raw"
        elif proj and folder in placed:
            dec = "already-placed"
        elif proj and placed:
            dec = "placed-elsewhere"
        elif proj:
            st = (projects.get(folder) or {}).get("status", "").strip().lower()
            dec = "closed-project" if st == "closed" else "place"
        elif placed:
            dec = "already-placed"
        elif f["holding12"]:
            dec = "already-in-holding"
        else:
            dec = "holding"
        root = ""
        if dec in ("place", "closed-project"):
            if reading.startswith("R4"):
                root = "|".join(H.norm(s) for s in A2P.NO_CODE_ROOTS[reading.split("-")[0]][0].split("\\"))
            else:
                root = root_of(rel, folder)
            if not root:
                raise SystemExit(f"STOP: no study folder for the PMOD export {rel} in {folder}")
        out.append({"relpath": rel, "top": f["top"], "size": f["size"], "sha256": f["sha256"], "cls": PMOD_CLASS,
                    "claim_id": f["claim_id"], "verdict": f["verdict"], "reading": reading, "dec_rec": dec,
                    "rec_project": proj, "dest": "", "root_rec": root, "placed12": f["placed12"],
                    "conflict": f["conflict"], "n1": "Y"})
    c = collections.Counter(r["dec_rec"] for r in out)
    say(f"N1 PMOD exports (stream N, A1 kind pmod-export): {len(out)} files, {len({r['sha256'] for r in out})} "
        f"distinct, {gb(sum(int(r['size']) for r in out))} GB; A2's first decision: {dict(c)}")
    return out


# ------------------------------------------------------------------------------ the manifest

def manifest_rows(work, projects, researcher):
    rows = []
    for i, w in enumerate(work, 1):
        proj = w["project"]
        prow = projects.get(proj) if proj else None
        name = w["member"] or w["relpath"]
        rows.append({
            "row": i, "drive": DRIVE, "drive_label": LABEL, "relpath": w["archive"] or w["relpath"],
            "archive": w["archive"], "member": w["member"], "size": w["size"], "sha256": w["sha256"],
            "class": w["cls"], "ext": file_ext(name.replace("/", "\\").split("\\")[-1]),
            "flag": "zero-byte" if int(w["size"]) == 0 else "",
            "claim_id": w["claim_id"], "verdict": w["verdict"], "researcher": researcher.get(w["relpath"], ""),
            "project_name": proj if w["decision"] in ("place", "held", "already-placed", "expanded",
                                                      "duplicate-copy") else "",
            "project_id": (prow["project_id"] if prow else ("NEW" if proj else "")),
            "project_status": (prow["status"] if prow else ("" if not proj else "not-in-registry")),
            "dest_rel": "", "decision": w["decision"], "reason": reason_of(w), "note": w["note"],
            "root_key": w["root"] if w["root"] else "-", "shortened": "", "why": "", "why_detail": "",
            "hold": w["hold"]})
    return rows


def tree_base_of(r, projects):
    return NP.tree_base(r, projects)


def write_overlay(main_out, rows_held, projects, nas, overlay):
    """For every tree the held rows would land in: the _PATHMAP.csv / _INDEX.csv that tree will have once
    THIS manifest's place rows are published (the NAS documents merged with this run's previews), so held
    rows are planned exactly as a later release would plan them if nothing else changes the tree."""
    manifest = os.path.join(main_out, "placement_manifest.csv")
    for base in sorted({tree_base_of(r, projects) for r in rows_held}):
        dst = os.path.join(overlay, base)
        os.makedirs(dst, exist_ok=True)
        if os.path.exists(os.path.join(NP.tree_preview_dir(manifest, base), H.INDEX_NAME)):
            docs = NP.tree_documents(manifest, base, nas=nas)
            for name in (H.INDEX_NAME, H.PATHMAP_NAME):
                with open(os.path.join(dst, name), "wb") as f:
                    f.write(docs[f"{base}\\{name}"])
        else:
            for name in (H.INDEX_NAME, H.PATHMAP_NAME):
                src = os.path.join(nas, base, name)
                if os.path.exists(NP.lp(src)):
                    shutil.copyfile(NP.lp(src), os.path.join(dst, name))


def plan_held(rows, main_out, sub, projects, nas, say, override=None):
    """Destinations for the `held` rows (informational; `release` plans them again for real)."""
    held = [r for r in rows if r["decision"] == "held"]
    if not held:
        return {}
    out = os.path.join(main_out, sub)
    tmp = [dict(r, decision="place", project_name=(override or r["project_name"])) for r in held]
    overlay = os.path.join(out, "_overlay_nas")
    if os.path.isdir(overlay):
        shutil.rmtree(overlay)
    write_overlay(main_out, tmp, projects, nas, overlay)
    say(f"\nHELD rows ({len(held)}), planned as if this manifest's place rows were published "
        f"({sub}{', project ' + override if override else ''}):")
    NP.assign_destinations(tmp, projects, overlay, out, say, {}, None)
    return {r["row"]: (r["dest_rel"], r["shortened"]) for r in tmp}


# ------------------------------------------------------------------------------------ checks

def check_invariants(rows, manifest, projects, nas, say, stat_all=True):
    """The gate's invariants. -> list of failures (empty = all hold)."""
    fails = []

    def ok(cond, msg):
        say(f"  {'PASS' if cond else 'FAIL'}  {msg}")
        if not cond:
            fails.append(msg)

    # 1. every file's bytes = the drive manifest (members: their zip's bytes were checked at plan time)
    bad = [r for r in rows if not r["archive"] and (int(r["size"]), r["sha256"]) != manifest.get(r["relpath"])]
    ok(not bad, f"every row's (size, SHA-256) equals the drive manifest ({len(rows) - len(bad)} of {len(rows)}; "
                f"archive members are checked through their zip)")
    # 2. each drive file decided once
    keys = collections.Counter((r["relpath"], r["member"]) for r in rows)
    dup = [k for k, n in keys.items() if n > 1]
    ok(not dup, f"each file (or archive member) has exactly one decision ({len(keys)} distinct)")
    # 3. nothing both placed (or in holding) and held
    placed = {(r["relpath"], r["member"]) for r in rows if r["decision"] in ("place", "holding")}
    held = {(r["relpath"], r["member"]) for r in rows if r["decision"] == "held"}
    ok(not (placed & held), f"no file both copied now and held ({len(placed)} copied, {len(held)} held)")
    # 4. budget and uniqueness
    dests = [r["dest_rel"] for r in rows if r["decision"] in ("place", "holding", "held")]
    lens = [H.unc_len(d) for d in dests]
    ok(all(dests) and max(lens) <= H.BUDGET,
       f"every destination at most {H.BUDGET} characters on \\\\GJESUS3\\gjesus3\\ (longest {max(lens)}; "
       f"{len(dests)} destinations)")
    ok(all(len(c) <= H.COMPONENT_MAX for d in dests for c in d.split("\\")), "no path component over 255")
    low = collections.Counter(d.lower() for d in dests)
    ok(max(low.values()) == 1, "every destination is unique (case-insensitive), held ones included")
    ok(all(f"\\{TAG}\\" in d for d in dests), f"every destination is under a {TAG}\\ folder")
    # 5. projects
    inactive = sorted({r["project_name"] for r in rows if r["decision"] == "place"
                       and (projects.get(r["project_name"]) or {}).get("status", "").strip().lower() != "active"})
    ok(not inactive, f"every place row targets an ACTIVE project in the live registry ({inactive or 'all active'})")
    # 6. the staged copy's 7 verify problems (AppleDouble files the NAS rewrote) are never copied
    probs = {r["relpath"] for r in it(VERIFY_PROBLEMS)} if os.path.exists(VERIFY_PROBLEMS) else set()
    hit = [r for r in rows if r["relpath"] in probs and r["decision"] in ("place", "holding", "held")]
    ok(not hit, f"none of the staged copy's {len(probs)} verify problems is copied or held")
    # 7. biomaGUNE MJ is deferred, all of it
    bmj = [r for r in rows if r["relpath"].startswith("biomaGUNE MJ\\") and r["decision"] != "deferred"]
    ok(not bmj, "nothing under biomaGUNE MJ is placed, held or put in holding (deferred by Ryan's order)")
    # 8. no collision with an existing file: no target tree has a MJesus-MFB folder yet, and no
    #    destination exists
    bases = sorted({d.split(f"\\{TAG}\\")[0] for d in dests})
    pre = [b for b in bases if os.path.exists(NP.lp(os.path.join(nas, b, TAG)))]
    ok(not pre, f"no target tree has a {TAG}\\ folder yet ({len(bases)} trees checked: {pre or 'none'})")
    if stat_all:
        hits = [d for d in dests if os.path.exists(NP.lp(os.path.join(nas, d)))]
        ok(not hits, f"no destination exists on the NAS ({len(dests)} stat'ed)")
    # 9. every duplicate-copy / covered-by-twin points at a copy that is placed, held or already there
    by_path = {(r["relpath"] + ("!" + r["member"] if r["member"] else "")): r for r in rows}
    orphan = []
    for r in rows:
        if r["decision"] == "duplicate-copy":
            m = re.match(r"canonical \((\w[\w-]*)\): (.*)$", r["note"])
            c = by_path.get(m.group(2)) if m else None
            if not c or c["decision"] not in ("place", "held", "holding"):
                orphan.append(r["relpath"])
    ok(not orphan, f"every duplicate-copy's canonical copy is placed, held or in holding ({len(orphan)} orphans)")
    return fails


# ----------------------------------------------------------------------------------- compare

def compare_with_a2(work, rows):
    """Every row against A2's plan: same decision and destination, or the call that changed it."""
    out = []
    by_key = {}
    for w, r in zip(work, rows):
        by_key[(w["relpath"], w["member"])] = (w, r)
    stats = collections.Counter()
    for (rel, mem), (w, r) in by_key.items():
        a2d, a2p, a2dest = w["a2_dec"], w["a2_project"], w["a2_dest"]
        new_dest = r["dest_rel"] if r["decision"] in ("place", "holding", "held") else ""
        if mem:
            cause = "P1 archive member (new row)"
        elif w.get("n1"):
            cause = "N1 PMOD export (not in A2's plan; stream N)"
        elif r["decision"] == "expanded":
            cause = "P1 archive expanded, not copied whole"
        elif w["call"].startswith("C5"):
            cause = "C5 model output -> holding"
        elif w["call"].startswith("C4"):
            cause = "C4 D5: also placed in drive 3's project"
        elif a2p in A2_0118_NAMES and r["decision"] in ("place", "held"):
            cause = "C2 0118 under AE-biomaGUNE-0118" + (" (held, M1)" if r["decision"] == "held" else " (Monocrotalina, placed)")
        elif a2d == "closed-project":
            cause = "C3 closed project: held"
        elif a2d == "place-after-reopen":
            cause = "C1 1121 reopened"
        else:
            cause = ""
        dec_map = {"place": "place", "place-after-reopen": "place", "closed-project": "held",
                   "duplicate-copy": "duplicate-copy", "covered-by-twin": "covered-by-twin", "holding": "holding",
                   "deferred-biomaGUNE-MJ": "deferred", "exclude-zero-byte": "exclude",
                   "already-placed": "already-placed", "already-in-holding": "already-in-holding",
                   "placed-elsewhere": "placed-elsewhere"}
        same_dec = dec_map.get(a2d) == r["decision"] or (a2p in A2_0118_NAMES and r["decision"] == "held" and a2d == "place")
        a2_tail = a2dest.split("\\historical_drives\\", 1)[-1] if a2dest else ""
        new_tail = new_dest.split("\\historical_drives\\", 1)[-1] if new_dest else ""
        same_dest = (a2dest == new_dest) or (cause.startswith(("C2", "C3", "C1")) and a2_tail == new_tail)
        if not cause and not same_dec:
            cause = "side effect: content level / dedup re-run"
        if not cause and a2dest and new_dest and not same_dest:
            cause = "side effect: shortening re-planned (the tree's file set changed)"
        kind = "same" if (not cause and same_dec and (same_dest or not a2dest)) else cause
        stats[(kind, a2d, r["decision"], "dest same" if same_dest else ("dest differs" if a2dest or new_dest else ""))] += 1
        if kind != "same":
            out.append({"relpath": rel, "member": mem, "a2_decision": a2d, "a2_project": a2p, "a2_dest": a2dest,
                        "decision": r["decision"], "project": r["project_name"], "hold": r["hold"],
                        "dest": new_dest, "dest_tail_same": "Y" if a2_tail == new_tail else "N", "cause": kind})
    return out, stats


# ---------------------------------------------------------------------------------- commands

def junk_summary(say):
    tally = collections.Counter()
    owners = collections.Counter()
    ownb = collections.Counter()
    for r in it(A2_FILES):
        owners[r["owner"]] += 1
        ownb[r["owner"]] += int(r["size"] or 0)
        if r["owner"] == "junk":
            tally[r["detail"]] += 1
    say(f"\ndrive files by owner (A2's files.csv): " + ", ".join(f"{k} {owners[k]:,} ({gb(ownb[k])} GB)" for k in sorted(owners)))
    say("excluded junk (never placed), by reason:")
    for k, v in tally.most_common():
        say(f"  {v:6,d}  {k}")
    return owners, tally


A3_MODEL_SETS = ("S-CINE-PRED-VICOMTECH", "S-RAT-2DG-2019-PRED")   # A3 S6: model output, not ground truth


def check_c5_against_a3(work, say):
    """C5's selector (model_output) against A3's own sets: every A3 S6 label outside biomaGUNE MJ is selected,
    and every selected file is such a label, its MetaImage .raw, or another file of a Predict_Slicer folder.
    -> list of problems."""
    labels = {r["relpath"] for r in it(A3_LABELS) if r["set_id"] in A3_MODEL_SETS}
    labels = {x for x in labels if not x.startswith("biomaGUNE MJ\\")}
    sel = {w["relpath"] for w in work if w["call"].startswith("C5")}
    missed = sorted(labels - sel)
    companions = {os.path.splitext(x)[0].lower() for x in labels if x.lower().endswith(".mhd")}
    odd = sorted(x for x in sel - labels if not (os.path.splitext(x)[0].lower() in companions and x.lower().endswith(".raw"))
                 and "\\predict_slicer\\" not in x.lower())
    say(f"\nC5 against A3's model-output sets: {len(labels)} A3 labels outside biomaGUNE MJ, {len(sel)} files "
        f"selected; A3 labels not selected {len(missed)}; selected files that are neither a label, its .raw nor "
        f"in a Predict_Slicer folder {len(odd)}")
    return [f"C5 missed {x}" for x in missed] + [f"C5 selected {x}" for x in odd]


def cmd_plan(args):
    stdout_utf8()
    out = args.out
    os.makedirs(out, exist_ok=True)
    log = []

    def say(m=""):
        print(m, flush=True)
        log.append(m)

    say(f"p_plan plan {dt.datetime.now():%Y-%m-%d %H:%M}  nas={args.nas}  out={out}")
    projects = load_projects(args.nas)
    manifest, msha = verify_drive_manifest(say)
    a2rows = rd(A2_PLAN)
    say(f"A2 plan rows: {len(a2rows):,} ({A2_PLAN})")
    zm = zip_members_of(a2rows, manifest, say)
    root_of = claim_roots()
    if args.raw_index:
        raw_shas = {r["sha256"] for r in it(args.raw_index)}
        say(f"/raw/ (live index of today): {len(raw_shas)} distinct SHA-256 from {args.raw_index}")
    else:
        import p_verify
        raw_shas = {r["sha256"] for r in p_verify.live_raw_index(args.nas, say)}
    a2rows += pmod_rows(projects, raw_shas, root_of, say)                      # N1
    work = decide(a2rows, projects, root_of, zm)
    researcher = researchers([w["relpath"] for w in work])
    rows = manifest_rows(work, projects, researcher)

    # destinations: the copied rows (place, holding) against the live NAS, then the held rows
    NP.assign_destinations(rows, projects, args.nas, out, say, {}, None)
    held_u = plan_held(rows, out, "held_U", projects, args.nas, say)
    for r in rows:
        if r["row"] in held_u:
            r["dest_rel"], r["shortened"] = held_u[r["row"]]
    held_e = plan_held([r for r in rows if r["hold"] == HOLD_M1], out, "held_E", projects, args.nas, say,
                       override=P0118_E)
    m1 = [r for r in rows if r["hold"] == HOLD_M1]
    diff = []
    for r in m1:
        u, e = r["dest_rel"], held_e[r["row"]][0]
        tu = u.split("\\historical_drives\\", 1)[1]
        te = e.split("\\historical_drives\\", 1)[1]
        if tu != te:
            diff.append({"relpath": r["relpath"], "dest_U": u, "dest_E": e})
    wcsv(os.path.join(out, "m1_U_vs_E.csv"), ["relpath", "dest_U", "dest_E"], diff, bom=True)
    say(f"\nM1 (0118): {len(m1)} held rows; below historical_drives\\ the U and E plans differ for {len(diff)} "
        f"(only the base folder changes for the other {len(m1) - len(diff)}); longest under E: "
        f"{max((H.unc_len(v[0]) for v in held_e.values()), default=0)}")

    NP.wcsv(os.path.join(out, "placement_manifest.csv"), NP.MANIFEST_FIELDS, rows)
    write_reports(rows, work, out, say)
    owners, _junk = junk_summary(say)
    c5 = check_c5_against_a3(work, say)
    say("\nINVARIANTS")
    fails = check_invariants(rows, manifest, projects, args.nas, say, stat_all=not args.no_stat)
    say(f"  {'PASS' if not c5 else 'FAIL'}  C5 selects exactly A3's model outputs (and their companions)")
    fails += c5
    cmp_rows, stats = compare_with_a2(work, rows)
    wcsv(os.path.join(out, "compare_a2.csv"), ["relpath", "member", "a2_decision", "a2_project", "a2_dest", "decision",
                                               "project", "hold", "dest", "dest_tail_same", "cause"], cmp_rows, bom=True)
    say("\nAGAINST A2's PLAN (kind, A2 decision, this decision, destination): files")
    for k, v in sorted(stats.items(), key=lambda kv: (kv[0][0] != "same", kv[0])):
        say(f"  {v:7,d}  {k}")
    n1 = sum(1 for a in a2rows if a.get("n1"))             # A1-owned in A2's split, planned here (N1)
    total = len(a2rows) + owners.get("A1", 0) - n1 + owners.get("junk", 0)
    say(f"\nreconciliation: A2's rows {len(a2rows) - n1:,} + N1 {n1} + A1 {owners.get('A1', 0) - n1:,} (A2's split "
        f"{owners.get('A1', 0):,} less the N1 rows) + junk {owners.get('junk', 0):,} = {total:,}; drive manifest "
        f"{len(manifest):,} -> {'OK' if total == len(manifest) else 'MISMATCH'}")
    if total != len(manifest):
        fails.append("reconciliation with the drive manifest")
    with io.open(os.path.join(out, "plan.log"), "w", encoding="utf-8") as f:
        f.write("\n".join(log) + "\n")
    say(f"\n{'ALL INVARIANTS HOLD' if not fails else 'FAILED: ' + '; '.join(fails)}  -> {out}")
    return 1 if fails else 0


def write_reports(rows, work, out, say):
    """per_project.csv (files, bytes and a list hash per tree and decision) and the decision table."""
    agg = collections.defaultdict(lambda: [0, 0])
    for r in rows:
        agg[(r["decision"], r["project_name"] or ("(holding)" if r["decision"] == "holding" else ""), r["hold"])][0] += 1
        agg[(r["decision"], r["project_name"] or ("(holding)" if r["decision"] == "holding" else ""), r["hold"])][1] += int(r["size"])
    say("\nBY DECISION")
    dec = collections.defaultdict(lambda: [0, 0])
    for (d, _p, _h), (n, b) in agg.items():
        dec[d][0] += n
        dec[d][1] += b
    for d in ("place", "holding", "held") + LISTED_ONLY:
        if d in dec:
            say(f"  {d:20s} {dec[d][0]:8,d} files {gb(dec[d][1]):>8s} GB")
    prow = []
    for (d, p, h), (n, b) in sorted(agg.items()):
        if d not in ("place", "holding", "held"):
            continue
        sel = sorted((r["dest_rel"].lower(), r["sha256"]) for r in rows
                     if r["decision"] == d and (r["project_name"] or "(holding)") == p and r["hold"] == h)
        lh = hashlib.sha256("\n".join(f"{x}\t{y}" for x, y in sel).encode("utf-8")).hexdigest()
        prow.append({"decision": d, "project": p, "hold": h, "files": n, "bytes": b, "gb": gb(b), "list_sha256": lh})
    wcsv(os.path.join(out, "per_project.csv"), ["decision", "project", "hold", "files", "bytes", "gb", "list_sha256"], prow)
    say("\nPER PROJECT (copied now: place, holding; and held)")
    for p in prow:
        say(f"  {p['decision']:8s} {p['project']:28s} {p['hold']:28s} {p['files']:6,d} {p['gb']:>7s} GB  list {p['list_sha256'][:12]}")


def cmd_release(args):
    """Release HELD rows (an M1 answer, or a reopen): a NEW manifest holding only them, as `place`, with
    their destinations planned again against the live NAS. Refuses a project that is not active."""
    stdout_utf8()
    rows = rd(args.manifest)
    projects = load_projects(args.nas)
    sel = [r for r in rows if r["decision"] == "held" and r["hold"] == args.hold]
    if not sel:
        print(f"REFUSED: no held rows with hold {args.hold!r} in {args.manifest}")
        return 2
    proj = args.project or sel[0]["project_name"]
    if any(r["project_name"] != sel[0]["project_name"] for r in sel) and not args.project:
        print("REFUSED: the held rows name more than one project; pass --project")
        return 2
    prow = projects.get(proj)
    if prow is None or (prow.get("status") or "").strip().lower() != "active":
        print(f"REFUSED: {proj} is {'not in the registry' if prow is None else prow.get('status')}: "
              f"create it (create_project.py) or reopen it (reopen_project.py) first")
        return 2
    if os.path.normcase(os.path.abspath(args.out)) == os.path.normcase(os.path.abspath(os.path.dirname(args.manifest))):
        print("REFUSED: give a NEW --out folder (the batch manifest is the record)")
        return 2
    today = dt.date.today().isoformat()
    new = []
    for i, r in enumerate(sel, 1):
        base = r["reason"].split(HELD_SEP)[0]
        new.append(dict(r, row=i, decision="place", hold="", project_name=proj, project_id=prow["project_id"],
                        project_status=prow["status"], dest_rel="", shortened="",
                        reason=f"{base}; released {today} from hold {args.hold}"
                               + (f" into {proj}" if proj != r["project_name"] else "")))
    os.makedirs(args.out, exist_ok=True)
    NP.assign_destinations(new, projects, args.nas, args.out, print, {}, None)
    hits = [r["dest_rel"] for r in new if os.path.exists(NP.lp(os.path.join(args.nas, r["dest_rel"])))]
    NP.wcsv(os.path.join(args.out, "placement_manifest.csv"), NP.MANIFEST_FIELDS, new)
    print(f"release {args.hold}: {len(new)} files, {gb(sum(int(r['size']) for r in new))} GB -> {proj}; "
          f"destinations already present on the NAS: {len(hits)}; longest {max(H.unc_len(r['dest_rel']) for r in new)}")
    print(f"-> {os.path.join(args.out, 'placement_manifest.csv')}  (copy it with nonraw_placement.py copy "
          f"--manifest <that> --project {proj})")
    return 1 if hits else 0


HANDOVER_KINDS = ("derivative", "notregistered", "companion", "other")
JUNK_NAMES = {"desktop.ini": "ruled", "thumbs.db": "ruled", ".ds_store": "ruled",       # Ryan's list, 09-30
              "folders.cache": "A2's addition", "thumbs.cache": "A2's addition"}
WD_INSTALLERS = {"otros\\install western digital software for windows.exe",
                 "otros\\install western digital software for mac.dmg"}


def junk_reason(relpath):
    """The drive's junk, by A2's rules (a2_common.classify): '' if the file is not junk. A later batch must
    never place what batch 1 excluded (a stream's list of an exam folder can sweep a desktop.ini in)."""
    name = relpath.split("\\")[-1]
    low = name.lower()
    if low in JUNK_NAMES:
        return f"{JUNK_NAMES[low]}: {name}"
    if name.startswith("._"):
        return "ruled: macOS AppleDouble ._ file"
    if relpath.lower() in WD_INSTALLERS:
        return "ruled: WD installer"
    if low in ("icon\r", "icon"):
        return "A2's addition: macOS folder-icon file"
    if low.startswith("~$") or (low.startswith("~wrl") and low.endswith(".tmp")):
        return "A2's addition: Office temporary file"
    return ""


def cmd_handover(args):
    """A LATER BATCH for the same trees: files another stream hands over (stream C's .czi derivatives,
    stream N's PET companions, stream M's not-registered exam folders). Each is checked against the drive
    manifest, refused if an earlier batch already decided it, and planned with the same rule against the
    live NAS (so it lands inside the folders batch 1 created, never renaming one). -> a NEW manifest.

    CSV columns: relpath (required), kind (derivative | notregistered:<no-recon|non-image|conversion-failed>
    | companion | other), project (blank = holding), reason, parent_acq_ids (derivative), sha256 (optional)."""
    stdout_utf8()
    projects = load_projects(args.nas)
    manifest, _sha = verify_drive_manifest(print)
    earlier = {}
    in_tree = set()   # (project or "(holding)", sha256) already there: an earlier batch, or the NAS index
    for m in args.manifest:
        for r in it(m):
            earlier[(r["relpath"], r["member"])] = r["decision"]
            if r["decision"] in ("place", "holding"):
                in_tree.add((r["project_name"] or "(holding)", r["sha256"]))
    # /raw/ as it is NOW: every acquisition's checksums.json, read live (p_verify.live_raw_index), or the
    # index `p_verify.py raw-dedup --write-index` saved earlier the same day. Never the 10:30 analysis
    # index (prod_raw_sha256.csv): production moves (86 AxioScan acquisitions arrived at 11:03-11:21).
    if args.raw_index:
        prod = {r["sha256"] for r in it(args.raw_index)}
        print(f"/raw/ index: {len(prod)} distinct SHA-256 from {args.raw_index}")
    else:
        import p_verify
        prod = {r["sha256"] for r in p_verify.live_raw_index(args.nas)}
    root_of = claim_roots()
    work, refused = [], []
    seen_trees = set()

    def load_tree(project):
        """The NAS index of the tree a handover row lands in (any drive's rows): bytes already there."""
        if project in seen_trees:
            return
        seen_trees.add(project)
        if project == "(holding)":
            path = os.path.join(args.nas, NP.HOLDING_BASE, "manifest.csv")
        else:
            path = os.path.join(args.nas, "projects", NP.project_folder(project, projects), *NP.SUBDIR, H.INDEX_NAME)
        if os.path.exists(NP.lp(path)):
            for r in it(NP.lp(path)):
                if r.get("sha256") and r.get("new_path"):
                    in_tree.add((project, r["sha256"]))
    for h in rd(args.csv):
        rel = h["relpath"].strip()
        kind = (h.get("kind") or "").strip()
        proj = (h.get("project") or "").strip()
        why = ""
        if rel not in manifest:
            refused.append((rel, "not in the drive manifest"))
            continue
        size, sha = manifest[rel]
        if h.get("sha256") and h["sha256"].strip() != sha:
            refused.append((rel, "sha256 differs from the drive manifest"))
            continue
        junk = junk_reason(rel)
        # keep_despite_name=Y: the stream has looked inside and the NAME lies (stream M: four MATLAB 5.0 files
        # named folders.cache / thumbs.cache, one of 212 MB, in the CNIC pig folder). It lifts only the junk-NAME
        # rule, for that one path, and needs a reason; AppleDouble, installers and Office temp files stay refused.
        keep = (h.get("keep_despite_name") or "").strip().upper() == "Y"
        if junk and keep and rel.split("\\")[-1].lower() in JUNK_NAMES and (h.get("reason") or "").strip():
            print(f"  KEPT DESPITE ITS NAME {rel}: {(h.get('reason') or '').strip()}")
            junk = ""
        if junk:
            refused.append((rel, f"junk, never placed ({junk})"))
            continue
        if size == 0:
            refused.append((rel, "zero-byte: counted, never placed"))
            continue
        if (rel, "") in earlier:
            refused.append((rel, f"already decided in an earlier batch ({earlier[(rel, '')]})"))
            continue
        if sha in prod:
            refused.append((rel, "the same bytes are in /raw/ (raw in production is never copied)"))
            continue
        if kind.split(":")[0] not in HANDOVER_KINDS:
            refused.append((rel, f"unknown kind {kind!r}"))
            continue
        if kind.startswith("notregistered:"):
            sub = kind.split(":", 1)[1]
            if sub not in NP.NOTREG_WHY:
                refused.append((rel, f"unknown not-registered reason {sub!r}"))
                continue
            why = NP.NOTREG_WHY[sub]
        if kind == "derivative":
            parents = re.sub(r"\s+", "", h.get("parent_acq_ids") or "")
            if not parents:
                refused.append((rel, "a derivative needs parent_acq_ids"))
                continue
            call = f"R3 derivative of {parents} ({(h.get('reason') or 'derivative').strip()}); stream {args.stream} handover"
        else:
            call = f"stream {args.stream} handover ({kind}): {(h.get('reason') or '').strip()}".rstrip(": ")
        w = {"relpath": rel, "archive": "", "member": "", "size": size, "sha256": sha, "cls": kind.split(":")[0],
             "top": rel.split("\\")[0], "claim_id": "", "verdict": "", "reading": "", "a2_dec": "", "a2_project": "",
             "a2_dest": "", "root": "", "project": "", "decision": "", "hold": "", "call": call, "note": "",
             "held_was": "", "why": why, "why_detail": (h.get("reason") or "").strip() if why else ""}
        if proj:
            p, dec, hold, c3 = target(proj, rel, projects)
            if args.hold and dec == "place":     # e.g. a stream-M batch for 0118 before M1 is answered
                dec, hold, c3 = "held", args.hold, f"held by the handover (--hold {args.hold})"
            w.update(project=p, decision=dec, hold=hold, root=root_of(rel, p))
            if hold:
                w["call"] = call + HELD_SEP + c3
        else:
            w["decision"] = "holding"
        load_tree(w["project"] or "(holding)")
        if (w["project"] or "(holding)", sha) in in_tree:
            w["decision"] = "already-placed" if w["project"] else "already-in-holding"
            w["hold"] = ""
            w["note"] = "the same bytes are already in this tree (an earlier batch or another drive)"
        work.append(w)
    for rel, why in refused:
        print(f"  REFUSED {rel}: {why}")
    if not work:
        print("nothing to plan")
        return 2 if refused else 0
    content_and_dedup(work)
    rows = []
    for i, w in enumerate(work, 1):
        prow = projects.get(w["project"]) if w["project"] else None
        reason = w["call"]
        rows.append({"row": i, "drive": DRIVE, "drive_label": LABEL, "relpath": w["relpath"], "archive": "",
                     "member": "", "size": w["size"], "sha256": w["sha256"], "class": w["cls"],
                     "ext": file_ext(w["relpath"].split("\\")[-1]), "flag": "", "claim_id": "", "verdict": "",
                     "researcher": "", "project_name": w["project"],
                     "project_id": prow["project_id"] if prow else "", "project_status": prow["status"] if prow else "",
                     "dest_rel": "", "decision": w["decision"], "reason": reason, "note": w["note"],
                     "root_key": w["root"] or "-", "shortened": "", "why": w["why"], "why_detail": w["why_detail"],
                     "hold": w["hold"]})
    os.makedirs(args.out, exist_ok=True)
    NP.assign_destinations(rows, projects, args.nas, args.out, print, {}, None)
    hits = [r["dest_rel"] for r in rows if r["dest_rel"] and os.path.exists(NP.lp(os.path.join(args.nas, r["dest_rel"])))]
    NP.wcsv(os.path.join(args.out, "placement_manifest.csv"), NP.MANIFEST_FIELDS, rows)
    c = collections.Counter(r["decision"] for r in rows)
    print(f"handover ({args.stream}): {len(rows)} files {dict(c)}; refused {len(refused)}; destinations already "
          f"present: {len(hits)} -> {os.path.join(args.out, 'placement_manifest.csv')}")
    return 1 if hits or refused else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--nas", default=NP.NAS_DEFAULT)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--out", default=OUT_DEFAULT)
    p.add_argument("--no-stat", action="store_true", help="skip stat'ing every destination on the NAS")
    p.add_argument("--raw-index", default="", help="a live /raw/ index saved today by p_verify.py raw-dedup "
                                                   "--write-index (default: read every checksums.json now)")
    r = sub.add_parser("release")
    r.add_argument("--manifest", required=True)
    r.add_argument("--hold", required=True, help="e.g. M1-0118, reopen-AE-biomaGUNE-1521")
    r.add_argument("--project", default=None, help="the project the answer names (M1 E: Proyecto-0118-rats-hipoxia)")
    r.add_argument("--out", required=True)
    h = sub.add_parser("handover")
    h.add_argument("--manifest", action="append", required=True, help="every earlier batch's manifest")
    h.add_argument("--csv", required=True)
    h.add_argument("--stream", required=True, help="who hands it over: C, N, M ...")
    h.add_argument("--hold", default="", help="hold every row that would be placed (e.g. M1-0118 before M1 is answered)")
    h.add_argument("--raw-index", default="", help="a live /raw/ index saved by p_verify.py raw-dedup --write-index "
                                                   "(default: read every checksums.json now)")
    h.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    return {"plan": cmd_plan, "release": cmd_release, "handover": cmd_handover}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
