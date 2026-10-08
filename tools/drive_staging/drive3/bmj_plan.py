#!/usr/bin/env python3
"""bmj_plan.py -- `biomaGUNE MJ`, M. Jesus's own working folder on drive 3: the THIRD placement batch of
stream P's tool (its later-batch path, `p_plan.py handover`, as stream M's P2 used). Record:
tasks/drive3_biomagune_mj_gate.md.

Input: the 26,410 rows that stream P's executed manifest marked `deferred`. `lists` decides each of them
and writes the hand-over list for `p_plan.py handover`; `check` reconciles the batch manifest handover
built with those decisions, checks the invariants and prints the gate's tables.

    set PYTHONDONTWRITEBYTECODE=1
    python tools/drive_staging/drive3/bmj_plan.py lists --raw-index CSV --out DIR
    python tools/drive_staging/drive3/p_plan.py handover --manifest <every earlier batch> --csv DIR\\bmj_handover.csv
                                                          --stream BMJ --raw-index CSV --out BATCH
    python tools/drive_staging/drive3/bmj_plan.py check --lists DIR --batch BATCH\\placement_manifest.csv --raw-index CSV
    python tools/drive_staging/drive3/bmj_plan.py readme --project AE-biomaGUNE-0619 [--execute]   (a README-only tree)

READ-ONLY on J: (production and the staged copy alike). Writes only under --out / --lists.

THE RULES, per file, in this order
  untouched  under the Biodonostia Axioscan folder (`Manosa and 2DG Male_Proyecto 1422\\Raw data\\Microscopio\\
             Microscopio-biodonostia`): decided separately (STATUS), never planned here.
  personal   personal or administrative, judged by NAME only (never opened): never into a shared project
             folder, neither placed nor held; listed for Ryan by folder and count. A broad keyword screen
             (SCREEN) runs over every path; each hit is judged by an explicit table (JUDGED). A hit the table
             does not know STOPS the run, so nothing new slips through unjudged.
  zero-byte  counted, never placed (the drives 1+2 rule).
  in-raw     the exact bytes are an acquisition file in /raw/ (a live index, p_verify.py raw-dedup).
  zip-twin   an archive whose bytes are an archive batch 1 expanded (P1): its members are already placed.
  C5         the model outputs (A3 S6, stream P's call C5: every file in a `Predict_Slicer` folder, the Vicomtech
             predictions) go to the holding folder, beside the group's tool, whatever their folder's claim.
  project    the claims engine's per-file verdict (Ryan's rule of 2026-09-29; A2's claims\\), and, for the
             folders whose NAME gives two protocols (`PAH aged_Proyecto 0424 & 1019 (female and male)`,
             `PAH diets_Proyecto 0619 & 0522 ...`, `PAH female and male_(Proyecto 0522 & 0619)`):
               TWO  such a folder makes no claim of its own: a file whose deciding claim IS that folder has no
                    project (A2's precedent, `Pili y Mili\\Proyecto 1019 + 1121`: all (C)), also where the
                    engine read one of the two codes and called it CONFIRMED;
               R5   a NEARER single-code claim the engine CONFIRMED, whose code the two-code folder also gives,
                    stands when the engine's only disagreement is with that folder (and with tokens the engine
                    never confirmed as a protocol, such as the YYMM `2303`), and the file's own evidence is
                    inconclusive, not contrary ("no animal number to decide between them", or "animal N is
                    found in BOTH ... and the DB dates do not separate them"): the engine read the folder as
                    one code and saw a disagreement where the folder agrees (as A2's R2);
               R3b  a YYMM date folder that the engine itself "reads as a date" is the nearest claim: read the
                    next single-code claim outward (A2's R3), when the two-code folder also gives that code.
             (B) per code (Project-0521 only); anything else -- (C), no claim -- has no project.
  dedup      SHA-256 only. A file with a project whose bytes are already in that project's tree (any drive,
             any batch): `already-placed` (handover, from the tree's live _INDEX.csv). A file with NO project
             whose bytes are in ANY project tree, or go to a project in this batch: `covered-by-twin` (A2's
             rule). In the holding folder: `already-in-holding` (handover). Within the batch: one study folder
             per content (handover, A2 D3).
"""
import argparse
import collections
import csv
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.dirname(HERE)
TOOLS = os.path.dirname(DS)
for _p in (TOOLS, DS, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import historical_paths as H  # noqa: E402
import nonraw_placement as NP  # noqa: E402
import p_plan as P  # noqa: E402  (stream P's C5 rule: model_output)

ANALYSIS = r"D:\projects\gjesus3\drive3_analysis"
A2_FILES = os.path.join(ANALYSIS, "a2", "files.csv")
A2_CLAIMS = os.path.join(ANALYSIS, "a2", "claims", "claims.csv")
P_MANIFEST = r"D:\projects\gjesus3\drive3_streams\placement\manifest_check2_20261006\placement_manifest.csv"
BMJ = "biomaGUNE MJ\\"
BIODONOSTIA = BMJ + "Manosa and 2DG Male_Proyecto 1422\\Raw data\\Microscopio\\Microscopio-biodonostia\\"
DATE_EVIDENCE = "reads as a date close to its files' dates"
NESTED_RE = re.compile(r"nested claims disagree: nearest (\d{4}) \((\w+)\) vs outer ([\d,]+); (.*)$")
INCONCLUSIVE_RE = re.compile(r"no animal number to decide between them|"
                             r"animal \d+ is found in BOTH .* and the DB dates do not separate them")
CODE_RE = re.compile(r"(?<!\d)(\d{4})(?!\d)")
STREAM = "BMJ"

# The personal / administrative screen: deliberately broad (CVs, contracts, payslips, ID documents, private
# correspondence, personal photos). It reads NAMES only.
SCREEN = re.compile(
    r"(?i)(\bcv\b|curric|contrat|contract|n[oó]mina|payslip|payroll|\bdni\b|\bnie\b|pasaporte|passport|factur|"
    r"invoice|irpf|hacienda|\bbanco\b|\bbank|seguro|insurance|\bcarta\b|letter|personal|privad|private|\bfotos?\b|"
    r"photo|picture|\bimg_|whatsapp|vacacion|famil|boda|\brenta\b|salar|beca\b|certific|t[ií]tulo|viaje|travel|"
    r"billete|ticket|reserva|hotel|e-?mail|correo|ausencia|m[eé]dic|\bbaja\b|permiso|horario|jornada|"
    r"expediente|matr[ií]cula|selfie|screenshot|captura|recibo|receipt|admin|solicitud|gasto|expense|pedido|"
    r"presupuesto|budget\b|\.(msg|eml|vcf|pages|jpe?g|heic|mov|mp4)$)")
# Every screen hit, judged: (pattern on the path below biomaGUNE MJ, verdict, why). First match wins.
JUDGED = [
    (r"(?i)(^|\\)IMG_\d{8}_\d{6}\.jpe?g$", "personal", "a phone-camera photo (by its name; not opened)"),
    (r"(?i)_picture\.jpe?g$", "personal", "a picture named after a person (by its name; not opened)"),
    (r"(?i)en mi ausencia", "personal", "a note whose name refers to the owner's absence (not opened)"),
    (r"(?i)for-ep-?\d\dv?\d*_formulario_de_", "project", "a CEEA / OH project form (animal-protocol paperwork)"),
    (r"(?i)(^|\\)admin_[^\\]*Quantification Cq Results\.xlsx$", "project",
     "a qPCR instrument export ('admin' is the instrument's user account)"),
    (r"(?i)(^|\\)Solicitud_Unidad_Microscopia", "project", "a service request to the microscopy unit"),
    (r"(?i)(^|\\)ID_\d+_Flurpiridaz_\d{4}\.jpe?g$", "project", "a PET image export named by animal and tracer"),
    (r"(?i)(^|\\)FIGURA PAPER\.jpe?g$", "project", "a paper figure"),
    (r"(?i)(^|\\)Leyenda PCA[^\\]*\.pages$", "project", "an analysis legend (Apple Pages)"),
]


def it(path):
    with io.open(NP.lp(path), encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)


def rd(path):
    return list(it(path))


def gb(n):
    return f"{n / 1e9:.2f}"


def stdout_utf8():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="backslashreplace")
        except AttributeError:
            pass


# ----------------------------------------------------------------------------------------- the rules

def judge_personal(rel):
    """'' (not a screen hit, or judged project material) or 'personal'; -> (verdict, why). STOP on an
    unjudged hit."""
    below = rel[len(BMJ):] if rel.startswith(BMJ) else rel
    if not SCREEN.search(below):
        return "", ""
    for pat, verdict, why in JUDGED:
        if re.search(pat, below):
            return ("personal" if verdict == "personal" else "screened-project"), why
    raise SystemExit(f"STOP: the personal/administrative screen hit a name nobody has judged: {rel!r} "
                     f"(add it to JUDGED in bmj_plan.py, with its verdict)")


def two_code_folders(rels, projects):
    """{folder path: [codes]} for every folder on these paths whose NAME gives two (or more) protocols that are
    gjesus3 projects (`PAH aged_Proyecto 0424 & 1019 (female and male)`)."""
    out = {}
    for rel in rels:
        parts = rel.split("\\")
        for i in range(1, len(parts) - 1):
            codes = sorted({c for c in CODE_RE.findall(parts[i]) if f"AE-biomaGUNE-{c}" in projects})
            if len(codes) >= 2:
                out["\\".join(parts[: i + 1])] = codes
    return out


class Claims:
    """A2's claims (the engine's output, unchanged) with what the two-code rules need."""

    def __init__(self, rows):
        self.by_id = {c["claim_id"]: c for c in rows}
        self.confirmed_tokens = {c["token"] for c in rows if c["verdict"] in ("CONFIRMED", "A")}
        self.folder_claims = collections.defaultdict(list)
        for c in rows:
            if c["source"] == "folder":
                self.folder_claims[c["claim_root"]].append(c)

    def next_single_code(self, root, twofold):
        """The nearest folder claim OUTSIDE `root` (CONFIRMED / A, not a two-code folder), or None."""
        parts = root.split("\\")
        for i in range(len(parts) - 1, 0, -1):
            pre = "\\".join(parts[:i])
            if pre in twofold:
                continue
            ok = [c for c in self.folder_claims.get(pre, ()) if c["verdict"] in ("CONFIRMED", "A") and c["proposed_project"]]
            if ok:
                return ok[0]
        return None


def project_of(f, claims, twofold):
    """(project or '', rule, verdict as applied, why) for one file, by the rules in the module docstring."""
    v, prop, conf = f["verdict"], f["proposed_project"], f["conflict"]
    c = claims.by_id.get(f["claim_id"])
    encl = [k for k in twofold if f["relpath"].startswith(k + "\\")]
    codes = set(c_ for k in encl for c_ in twofold[k])
    if v in ("CONFIRMED", "A") and prop:
        if c is not None and c["claim_root"] in twofold:
            return "", "TWO", "C", (f"the deciding claim {c['claim_id']} is a folder that gives two protocols "
                                    f"({' & '.join(twofold[c['claim_root']])}); the engine read one of them")
        return prop, "engine", v, ""
    if v == "B":
        p = NP.B_PROJECTS.get(prop, "")
        return p, ("engine" if p else ""), v, ("" if p else f"(B) {prop}: no project")
    if v == "C" and encl and c is not None:
        m = NESTED_RE.match(conf)
        if m and c["claim_root"] not in twofold:
            near, nv, outer, why = m.group(1), m.group(2), m.group(3).split(","), m.group(4)
            if (nv in ("CONFIRMED", "A") and near in codes and c["token"] == near and c["proposed_project"]
                    and all(t in codes or t == near or t not in claims.confirmed_tokens for t in outer)
                    and INCONCLUSIVE_RE.search(why)):
                return c["proposed_project"], "R5", "C", (
                    f"R5: the nearer claim {c['claim_id']} ({near}, CONFIRMED) stands; its only disagreement is "
                    f"the folder that gives {' & '.join(sorted(codes))}")
            if nv == "C" and DATE_EVIDENCE in c.get("evidence", ""):
                nxt = claims.next_single_code(c["claim_root"], twofold)
                if nxt is not None and nxt["token"] in codes:
                    return nxt["proposed_project"], "R3b", "C", (
                        f"R3b: {c['token']} is a date folder; the next claim out, {nxt['claim_id']} ({nxt['token']}), "
                        f"is given by the folder of {' & '.join(sorted(codes))} too")
    return "", "", v, ""


# --------------------------------------------------------------------------------------- live state

def tree_shas(nas, projects, where=None):
    """sha256 -> {project} for every file the project trees' _INDEX.csv on the NAS lists as there (any drive,
    any batch), and the set of sha256 in the holding folder's manifest.csv. Read-only. `where` (a dict), if
    given, also gets sha256 -> [(project, new_path)]."""
    by_sha = collections.defaultdict(set)
    n = 0
    for name in sorted(projects):
        p = os.path.join(nas, "projects", NP.project_folder(name, projects), *NP.SUBDIR, H.INDEX_NAME)
        if os.path.exists(NP.lp(p)):
            for r in it(p):
                if r.get("new_path") and r.get("sha256"):
                    by_sha[r["sha256"]].add(name)
                    if where is not None:
                        where.setdefault(r["sha256"], []).append((name, r["new_path"]))
                    n += 1
    hold = set()
    hp = os.path.join(nas, NP.HOLDING_BASE, "manifest.csv")
    for r in it(hp):
        if r.get("new_path") and r.get("sha256"):
            hold.add(r["sha256"])
    return by_sha, hold, n


# ------------------------------------------------------------------------------------------- lists

DEC_FIELDS = ["relpath", "size", "sha256", "class", "engine_verdict", "claim_id", "engine_project", "rule",
              "verdict", "project", "pre_decision", "reason", "screen", "note"]
HANDOVER_FIELDS = ["relpath", "kind", "project", "reason", "parent_acq_ids", "sha256", "class", "claim_id", "verdict"]


def cmd_lists(args):
    stdout_utf8()
    os.makedirs(args.out, exist_ok=True)
    log = []

    def say(m=""):
        print(m, flush=True)
        log.append(m)

    projects = NP.load_projects(args.nas)
    batch1 = rd(P_MANIFEST)
    dfr = [r for r in batch1 if r["decision"] == "deferred"]
    say(f"batch 1 ({P_MANIFEST}): {len(batch1):,} rows; deferred (biomaGUNE MJ): {len(dfr):,} files, "
        f"{gb(sum(int(r['size']) for r in dfr))} GB")
    want = {r["relpath"] for r in dfr}
    files = {r["relpath"]: r for r in it(A2_FILES) if r["relpath"] in want}
    if set(files) != want or any(not r["relpath"].startswith(BMJ) for r in dfr):
        raise SystemExit("STOP: a deferred row is not in A2's files.csv, or not under biomaGUNE MJ")
    claims = Claims(rd(A2_CLAIMS))
    twofold = two_code_folders(want, projects)
    say("folders whose name gives two protocols: " + "; ".join(f"{k[len(BMJ):]} ({' & '.join(v)})" for k, v in sorted(twofold.items())))
    raw = {r["sha256"] for r in it(args.raw_index)}
    say(f"/raw/ (live index): {len(raw):,} distinct SHA-256 from {args.raw_index}")
    placed_at = {}
    by_sha, hold, n_idx = tree_shas(args.nas, projects, placed_at)
    say(f"project trees on the NAS: {n_idx:,} placed files ({len(by_sha):,} distinct SHA-256); holding folder: "
        f"{len(hold):,} distinct SHA-256")
    expanded = {}
    for r in batch1:
        if r["decision"] == "expanded":
            expanded[r["sha256"]] = (r["project_name"], r["relpath"])

    dec = []
    for r in dfr:
        f = files[r["relpath"]]
        d = {"relpath": r["relpath"], "size": int(r["size"]), "sha256": r["sha256"], "class": r["class"],
             "engine_verdict": f["verdict"], "claim_id": f["claim_id"], "engine_project": f["proposed_project"],
             "rule": "", "verdict": f["verdict"], "project": "", "pre_decision": "", "reason": "", "screen": "", "note": ""}
        if (int(f["size"]), f["sha256"]) != (d["size"], d["sha256"]):
            raise SystemExit(f"STOP: batch 1 and A2 disagree on the bytes of {r['relpath']}")
        pv, why = judge_personal(r["relpath"])
        d["screen"] = why
        if r["relpath"].startswith(BIODONOSTIA):
            d.update(pre_decision="untouched", reason="the Biodonostia Axioscan folder: decided separately")
        elif pv == "personal":
            d.update(pre_decision="personal", reason=why)
        elif d["size"] == 0:
            d.update(pre_decision="exclude", reason="zero-byte: counted, not placed")
        elif d["sha256"] in raw:
            d.update(pre_decision="in-raw", reason="the same bytes are an acquisition file in /raw/")
        elif d["class"] == "archive" and d["sha256"] in expanded:
            p, src = expanded[d["sha256"]]
            d.update(pre_decision="already-placed", project=p,
                     reason=f"zip-twin: the identical archive {src} was expanded by batch 1 (P1); its members are in {p}")
        elif P.model_output(r["relpath"]):
            d.update(pre_decision="handover", rule="C5", reason=P.model_output(r["relpath"]))
        else:
            proj, rule, verdict, why2 = project_of(f, claims, twofold)
            d.update(project=proj, rule=rule, verdict=verdict, pre_decision="handover",
                     reason=why2 or ("claim " + f["verdict"] if proj else
                                     ("no claim" if f["verdict"] in ("", "NO-CLAIM") else "(C) claim")))
            if proj and projects.get(proj) is None:
                raise SystemExit(f"STOP: {proj} is not in the live registry ({r['relpath']})")
        dec.append(d)
    # a file with no project whose bytes are in a project tree, or go to a project in this batch: covered
    claimed_here = collections.defaultdict(set)
    for d in dec:
        if d["pre_decision"] == "handover" and d["project"]:
            claimed_here[d["sha256"]].add(d["project"])
    for d in dec:
        if d["pre_decision"] == "handover" and not d["project"]:
            where = sorted(by_sha.get(d["sha256"], set()) | claimed_here.get(d["sha256"], set()))
            if where:
                d.update(pre_decision="covered-by-twin",
                         note="same bytes " +
                         ("already in " if by_sha.get(d["sha256"]) else "placed by this batch in ") + ", ".join(where))
    # the hand-over list: everything still to decide by the tool (project or holding)
    ho = []
    for d in dec:
        if d["pre_decision"] != "handover":
            continue
        if d["project"] or d["rule"] == "C5":    # C5 is a decision (holding by call), not a mappable blank
            reason = d["reason"]
        else:
            reason = "no claim" if d["reason"] == "no claim" else "(C) claim"
        ho.append({"relpath": d["relpath"], "kind": "other", "project": d["project"], "reason": reason,
                   "parent_acq_ids": "", "sha256": d["sha256"], "class": d["class"], "claim_id": d["claim_id"],
                   "verdict": d["verdict"] if d["verdict"] != "NO-CLAIM" else ""})
    NP.wcsv(os.path.join(args.out, "bmj_decisions.csv"), DEC_FIELDS, dec)
    NP.wcsv(os.path.join(args.out, "bmj_handover.csv"), HANDOVER_FIELDS, ho)
    pers = [d for d in dec if d["pre_decision"] == "personal"]
    for d in pers:   # an identical copy an EARLIER batch already put in a project folder: Ryan's to judge too
        d["copies_in_projects"] = "; ".join(f"{p}: {np_}" for p, np_ in placed_at.get(d["sha256"], []))
    NP.wcsv(os.path.join(args.out, "bmj_personal_files.csv"), ["relpath", "size", "reason", "copies_in_projects"],
            pers)   # D: only -- file names stay out of the repo
    twins = collections.Counter(p for d in pers for p, _np in placed_at.get(d["sha256"], []))
    say(f"flagged personal files with an identical copy already in a project folder (an earlier batch): "
        f"{sum(1 for d in pers if d['copies_in_projects'])} of {len(pers)}; copies per project {dict(twins) or 'none'}")
    pf = collections.Counter(os.path.dirname(d["relpath"]) for d in pers)
    NP.wcsv(os.path.join(args.out, "bmj_personal_folders.csv"), ["folder", "files"],
            [{"folder": k, "files": v} for k, v in sorted(pf.items())])
    agg = collections.defaultdict(lambda: [0, 0])
    for d in dec:
        k = (d["pre_decision"], d["project"] or "-", d["rule"] or "-")
        agg[k][0] += 1
        agg[k][1] += d["size"]
    say("\nPRE-DECISIONS (pre_decision, project, rule): files, GB")
    for k, (n, b) in sorted(agg.items()):
        say(f"  {n:7,d} {gb(b):>7s}  {k}")
    scr = collections.Counter(d["screen"] for d in dec if d["screen"] and d["pre_decision"] != "personal")
    say(f"\npersonal / administrative screen: {sum(scr.values()) + len(pers)} hits; flagged personal {len(pers)} "
        f"in {len(pf)} folders; judged project material: {dict(scr)}")
    say(f"\nhand-over list: {len(ho):,} rows ({sum(1 for h in ho if h['project']):,} with a project, "
        f"{sum(1 for h in ho if not h['project']):,} for holding) -> {os.path.join(args.out, 'bmj_handover.csv')}")
    total = len(dec)
    if total != len(dfr) or len({d['relpath'] for d in dec}) != total:
        raise SystemExit("STOP: the decisions do not account for every deferred row exactly once")
    with io.open(os.path.join(args.out, "lists.log"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(log) + "\n")
    return 0


# -------------------------------------------------------------------------------------------- check

COPIED = ("place", "holding")


def cmd_check(args):
    """The gate's invariants and tables, from the decisions and the batch manifest (handover's)."""
    stdout_utf8()
    log = []
    fails = []

    def say(m=""):
        print(m, flush=True)
        log.append(m)

    def ok(cond, msg):
        say(f"  {'PASS' if cond else 'FAIL'}  {msg}")
        if not cond:
            fails.append(msg)

    projects = NP.load_projects(args.nas)
    dec = rd(os.path.join(args.lists, "bmj_decisions.csv"))
    batch = rd(args.batch)
    raw = {r["sha256"] for r in it(args.raw_index)}
    by_sha, hold, _n = tree_shas(args.nas, projects)
    dfr = {r["relpath"]: r for r in it(P_MANIFEST) if r["decision"] == "deferred"}
    brow = {r["relpath"]: r for r in batch}
    final = []
    for d in dec:
        b = brow.get(d["relpath"])
        dd = dict(d)
        if d["pre_decision"] == "handover":
            dd["decision"] = b["decision"] if b else "MISSING"
            dd["project"] = b["project_name"] if b else d["project"]
            dd["dest_rel"] = b["dest_rel"] if b else ""
            dd["root_key"] = b["root_key"] if b else ""
        else:
            dd["decision"], dd["dest_rel"], dd["root_key"] = d["pre_decision"], "", ""
        final.append(dd)
    say("INVARIANTS")
    ok(len(dec) == len(dfr) == len({d["relpath"] for d in dec}) and set(d["relpath"] for d in dec) == set(dfr),
       f"every deferred row of batch 1 is decided exactly once ({len(dec):,} of {len(dfr):,})")
    ho = {d["relpath"] for d in dec if d["pre_decision"] == "handover"}
    ok(set(brow) == ho and len(batch) == len(ho),
       f"the batch manifest holds exactly the handed-over rows ({len(batch):,} rows, {len(ho):,} handed over; "
       f"refused by handover: {len(ho - set(brow))})")
    ok(all((int(b["size"]), b["sha256"]) == (int(dfr[b["relpath"]]["size"]), dfr[b["relpath"]]["sha256"]) for b in batch),
       "every batch row's (size, SHA-256) equals batch 1's (= the drive manifest)")
    cop = [b for b in batch if b["decision"] in COPIED]
    ok(not [b for b in cop if b["sha256"] in raw], f"no file copied is in /raw/ (live index; {len(cop):,} copied)")
    ok(not [d for d in final if d["relpath"].startswith(BIODONOSTIA)],
       "nothing under the Biodonostia Axioscan folder is in this batch at all (its 20 files are untouched)")
    pers = {d["relpath"] for d in dec if d["pre_decision"] == "personal"}
    ok(not (pers & set(brow)), f"no personal/administrative file is placed or held ({len(pers)} listed for Ryan)")
    ok(not [b for b in cop if b["relpath"].split("\\")[-1].startswith("._") or int(b["size"]) == 0],
       "no junk or zero-byte file is copied")
    dests = [b["dest_rel"] for b in cop]
    lens = [H.unc_len(x) for x in dests]
    ok(all(dests) and (max(lens) if lens else 0) <= H.BUDGET,
       f"every destination at most {H.BUDGET} characters (longest {max(lens) if lens else 0}; {len(dests):,})")
    ok(all(len(c) <= H.COMPONENT_MAX for x in dests for c in x.split("\\")), "no path component over 255")
    low = collections.Counter(x.lower() for x in dests)
    ok(not low or max(low.values()) == 1, "every destination is unique (case-insensitive)")
    ok(all(f"\\{H.TAGS['D3']}\\" in x for x in dests), f"every destination is under a {H.TAGS['D3']}\\ folder")
    if not args.no_stat:
        hits = [x for x in dests if os.path.exists(NP.lp(os.path.join(args.nas, x)))]
        ok(not hits, f"no destination exists on the NAS ({len(dests):,} stat'ed; {len(hits)} present)")
    inactive = sorted({b["project_name"] for b in batch if b["decision"] == "place"
                       and (projects.get(b["project_name"]) or {}).get("status", "").strip().lower() != "active"})
    ok(not inactive, f"every place row targets an active project ({inactive or 'all active'})")
    dproj = {d["relpath"]: d["project"] for d in dec}
    ok(all(b["project_name"] == dproj[b["relpath"]] for b in batch if b["decision"] == "place"),
       "every place row lands in the project its claim (or listed reading) gives")
    ok(not [b for b in batch if b["decision"] == "place" and b["project_name"] in by_sha.get(b["sha256"], ())],
       "no file is placed into a tree that already holds its bytes (live _INDEX.csv)")
    if args.stat_twins:   # every file NOT copied as already placed: its copy in the tree is there, same size
        placed_at = {}
        tree_shas(args.nas, projects, placed_at)
        bad = []
        ap = [b for b in batch if b["decision"] == "already-placed"]
        for b in ap:
            cands = [np_ for p, np_ in placed_at.get(b["sha256"], []) if p == b["project_name"]]
            base = os.path.join(args.nas, "projects", NP.project_folder(b["project_name"], projects), *NP.SUBDIR)
            if not any(os.path.exists(NP.lp(os.path.join(base, c))) and
                       os.path.getsize(NP.lp(os.path.join(base, c))) == int(b["size"]) for c in cands):
                bad.append(b["relpath"])
        ok(not bad, f"every already-placed file's copy in its tree exists on the NAS with the same size "
                    f"({len(ap) - len(bad):,} of {len(ap):,} stat'ed)")
    twofold = two_code_folders([b["relpath"] for b in batch], projects)
    off = [b["relpath"] for b in batch if b["decision"] == "place" and any(
        b["relpath"].startswith(k + "\\") and b["project_name"][-4:] not in v for k, v in twofold.items())]
    ok(not off, f"every file placed from inside a folder that gives two protocols lands in one of them ({len(off)} do not)")
    a3 = {r["relpath"] for r in it(P.A3_LABELS) if r["set_id"] in P.A3_MODEL_SETS and r["relpath"].startswith(BMJ)}
    mo_placed = [b["relpath"] for b in batch if b["decision"] == "place" and (P.model_output(b["relpath"]) or b["relpath"] in a3)]
    ok(not mo_placed, f"C5: no model output is placed in a project ({len(a3)} A3 model-output labels here; "
                      f"{sum(1 for d in dec if d['rule'] == 'C5')} files selected by the C5 rule; placed: {len(mo_placed)})")
    ok(not [b for b in batch if b["decision"] == "holding" and (b["sha256"] in hold or b["sha256"] in by_sha)],
       "no file goes to holding whose bytes are already in holding or in any project tree")
    by_path = {b["relpath"]: b for b in batch}
    orphan = []
    for b in batch:
        if b["decision"] == "duplicate-copy":
            m = re.match(r"canonical \((\w[\w-]*)\): (.*)$", b["note"])
            c = by_path.get(m.group(2)) if m else None
            if not c or c["decision"] not in COPIED:
                orphan.append(b["relpath"])
    ok(not orphan, f"every duplicate-copy's canonical copy is copied ({len(orphan)} orphans)")
    ok(not [b for b in batch if b["decision"] not in COPIED + ("already-placed", "already-in-holding", "duplicate-copy")],
       "the batch has no decision other than place / holding / already-placed / already-in-holding / duplicate-copy")

    # tables
    say("\nBY FINAL DECISION (files, GB)")
    agg = collections.defaultdict(lambda: [0, 0])
    for d in final:
        agg[d["decision"]][0] += 1
        agg[d["decision"]][1] += int(d["size"])
    for k, (n, b) in sorted(agg.items(), key=lambda kv: -kv[1][0]):
        say(f"  {k:20s} {n:7,d} {gb(b):>7s}")
    say("\nCOPIED, per tree (files, GB) | already placed | duplicate copies not placed | by rule")
    per = collections.defaultdict(lambda: collections.Counter())
    perb = collections.defaultdict(lambda: collections.Counter())
    for d in final:
        t = d["project"] or "(holding)"
        per[t][d["decision"]] += 1
        perb[t][d["decision"]] += int(d["size"])
        if d["decision"] == "place":
            per[t]["rule:" + (d["rule"] or "-")] += 1
    rows = []
    for t in sorted(per, key=lambda t: (t == "(holding)", t)):
        c, b = per[t], perb[t]
        n = c["place"] + c["holding"]
        if not n and not c["already-placed"] and not c["duplicate-copy"]:
            continue
        rules = {k[5:]: v for k, v in c.items() if k.startswith("rule:")}
        say(f"  {t:22s} {n:6,d} {gb(b['place'] + b['holding']):>7s} | {c['already-placed']:6,d} {gb(b['already-placed']):>6s} "
            f"| {c['duplicate-copy']:6,d} {gb(b['duplicate-copy']):>6s} | {rules}")
        rows.append({"tree": t, "copy_files": n, "copy_gb": gb(b["place"] + b["holding"]),
                     "already_placed_files": c["already-placed"], "already_placed_gb": gb(b["already-placed"]),
                     "already_in_holding_files": c["already-in-holding"],
                     "duplicate_copy_files": c["duplicate-copy"], "duplicate_copy_gb": gb(b["duplicate-copy"]),
                     "rules": ";".join(f"{k}={v}" for k, v in sorted(rules.items()))})
    out = os.path.dirname(args.batch)
    NP.wcsv(os.path.join(out, "bmj_per_tree.csv"), list(rows[0].keys()) if rows else ["tree"], rows)
    fields = DEC_FIELDS + ["decision", "dest_rel", "root_key"]
    NP.wcsv(os.path.join(out, "bmj_final.csv"), fields, final)
    elsewhere = collections.Counter(b["project_name"] for b in batch if b["decision"] == "place" and by_sha.get(b["sha256"]))
    say(f"\nplaced although the same bytes sit in ANOTHER project's tree (A2 D5 / C4: the same file in two projects is "
        f"harmless): {dict(sorted(elsewhere.items())) or 'none'}")
    roots = collections.Counter((d["project"], d["root_key"].split("|")[-1] if d["root_key"] not in ("", "-") else "-")
                                for d in final if d["decision"] == "place")
    say("\nSTUDY FOLDERS of the placed rows (project, study folder): files")
    for (p, r), n in sorted(roots.items()):
        say(f"  {n:6,d}  {p}  {r}")
    say(f"\n{'ALL INVARIANTS HOLD' if not fails else 'FAILED: ' + '; '.join(fails)}")
    with io.open(os.path.join(out, "check.log"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(log) + "\n")
    return 1 if fails else 0


def cmd_readme(args):
    """The README.txt of trees that get a note (historical_paths.PROJECT_README_NOTES) but no file in this batch
    (0619: everything of it here is already placed or a model output): written alone, as `copy` would write it.
    A tool-owned document; its provenance row (`working/historical_drives/README.txt`, "rewritten when more
    material is added") is already there. Dry run unless --execute. -> 0, or 2 if a tree is missing."""
    stdout_utf8()
    projects = NP.load_projects(args.nas)
    rc = 0
    for proj in args.project:
        if proj not in H.PROJECT_README_NOTES or proj not in projects:
            print(f"REFUSED {proj}: no README note for it, or not in the registry")
            rc = 2
            continue
        base = "\\".join(["projects", NP.project_folder(proj, projects), *NP.SUBDIR])
        full = os.path.join(args.nas, base, H.README_NAME)
        if not os.path.exists(NP.lp(full)):
            print(f"REFUSED {proj}: {base} has no README.txt (no historical-drive tree)")
            rc = 2
            continue
        data = H.project_readme(base).replace("\n", "\r\n").encode("utf-8")
        with open(NP.lp(full), "rb") as fh:
            same = fh.read() == data
        if same:
            print(f"  {proj}: README.txt already carries the note (unchanged)")
        elif args.execute:
            print(f"  {proj}: README.txt {'written' if NP.write_if_changed(full, data) else 'unchanged'}")
        else:
            print(f"  {proj}: README.txt would be rewritten with the note (dry run)")
    return rc


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--nas", default=NP.NAS_DEFAULT)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("lists")
    a.add_argument("--raw-index", required=True, help="a live /raw/ index of today (p_verify.py raw-dedup --write-index)")
    a.add_argument("--out", required=True)
    c = sub.add_parser("check")
    c.add_argument("--lists", required=True)
    c.add_argument("--batch", required=True)
    c.add_argument("--raw-index", required=True)
    c.add_argument("--no-stat", action="store_true")
    c.add_argument("--stat-twins", action="store_true", help="also stat the tree copy of every already-placed file")
    r = sub.add_parser("readme")
    r.add_argument("--project", nargs="+", required=True)
    r.add_argument("--execute", action="store_true")
    args = ap.parse_args(argv)
    return {"lists": cmd_lists, "check": cmd_check, "readme": cmd_readme}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
