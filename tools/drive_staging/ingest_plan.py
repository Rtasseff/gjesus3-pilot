#!/usr/bin/env python3
"""ingest_plan.py -- turn the drives catalog + claims into a per-file ingest plan, a hard-link farm
and one generated ingest config per batch, for the historical `.czi` on the two staged drives.

ONE-TIME TOOL for the 2026-09/10 historical-microscopy-drives ingest (branch
feat/drives-microscopy-ingest). The decisions it implements are Ryan's of 2026-09-29 (CHANGELOG);
their per-file form is the table in tasks/drives_ingest_dryrun_review.md. The production procedure
is tasks/drives_microscopy_ingest_runbook.md.

    python tools/drive_staging/ingest_plan.py goptical [--hash]   # index S:\\goptical AxioScan (ZWSI check)
    python tools/drive_staging/ingest_plan.py plan                # -> <out>\\expected.csv, batches.csv, ...
    python tools/drive_staging/ingest_plan.py extract             # archive-only .czi -> _extract\\ (7-Zip)
    python tools/drive_staging/ingest_plan.py farm [--batch B01]  # hard-link farm -> _farm\\<batch>\\
    python tools/drive_staging/ingest_plan.py configs             # -> tools/configs/drives_2026-09/
    python tools/drive_staging/ingest_plan.py scratch --batch B01 # rehearsal NAS root on D: (never J:)

INPUTS (all regenerable, on D:): the catalog (tools/drive_staging/catalog.py: files.csv,
archive_members.csv, dup_groups.csv and a FRESH production_hashes.csv -- re-run `catalog.py
production` + `assemble` first), the claims (tools/drive_staging/project_claims.py: file_claims.csv,
archive_member_claims.csv, claims.csv), and J:\\gjesus3-data\\registries\\registry_projects.csv plus a
listing of each target project's raw_linked\\ (read-only).

WHAT IS IN SCOPE: every DISTINCT .czi content (by sha256) that is catalog class `czi-raw`, whose
device fingerprint is CELL / LSM9 / ZWSI / EXTERNAL:AxioImagerZ2 (-> XMIC), whose bytes are not
already in production, and -- for ZWSI -- that is not already in the AxioScan's own archive on
S:\\goptical (that route ingests it; a second root is how the 22 production duplicates happened).
A content that exists only inside an archive is in scope too (extracted, then farmed).

ONE CANONICAL COPY PER CONTENT, first rule that separates wins: (1) its claim gives a project;
(2) a loose copy outside `2025-10-02 - Toshiba EXT (Backup)`, then a loose backup copy, then an
archive member; (3) a non-blank researcher; (4) the shorter path; (5) D1 before D2; (6) lexicographic.
Copies that claim DIFFERENT projects are a conflict: listed in conflicts.csv, blank project.

PER-FILE VALUES (Ryan, 2026-09-29): instrument = fingerprint, never the folder. Project = the
claim's AE-biomaGUNE-NNNN for Confirmed and (A); blank for (C) and no-claim. Subject id = the claims
table's, Confirmed only ((A) = 0118 is HELD until Lucia confirms). Researcher = the innermost person
folder as written, EXCEPT under the operators' top folders (`Cell observer\\AINHIZE|Marta`,
`CELL OBSERVER 2\\AINHIZE|Marta`), which give the OPERATOR; elsewhere the operator is blank (ZWSI:
the filename's operator initials, the AxioScan convention). czi_user is never used; initials are
never mapped to people. data_source internal, XMIC `collaborator:Charite`. original_name =
`<drive-label>/<source relpath>` -- the farm is laid out so that the engine derives exactly that.

Writes only under <out> (default D:\\projects\\gjesus3\\staging\\_analysis\\ingest), _farm\\,
_extract\\ and the repo config folder. Never touches the staged drive trees.
"""
import argparse
import collections
import csv
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)
REPO = os.path.dirname(TOOLS)
sys.path.insert(0, HERE)
from stage_copy import CHUNK, longpath, load_manifest  # noqa: E402

STAGING = r"D:\projects\gjesus3\staging"
CAT = os.path.join(STAGING, "_analysis", "catalog")
CODES = os.path.join(STAGING, "_analysis", "codes")
OUT = os.path.join(STAGING, "_analysis", "ingest")
FARM = os.path.join(STAGING, "_farm")
EXTRACT = os.path.join(STAGING, "_extract")
NAS = r"J:\gjesus3-data"
GOPTICAL = r"S:\goptical\GOpticalUsers data\AxioScan"
SEVENZIP = r"C:\Program Files\7-Zip\7z.exe"
CONFIG_DIR = os.path.join(TOOLS, "configs", "drives_2026-09")
CONFIG_DIR_REL = "tools/configs/drives_2026-09"

# catalog drive -> (claims drive, farm label == first component of original_name, staged folder)
DRIVES = {
    "D1": ("drive1", "drive1_FRIO-X6", "drive1_FRIO-X6_2322E4A111E7"),
    "D2": ("drive2", "drive2_MFB-Disco-2", "drive2_MFB-Disco-2_2322E4A112BD"),
}
INSTRUMENTS = {"CELL": "CELL", "LSM9": "LSM9", "ZWSI": "ZWSI", "EXTERNAL:AxioImagerZ2": "XMIC"}
BACKUP_TOP = "2025-10-02 - Toshiba EXT (Backup)"
# (drive, top folder, operator folder) -- matched case-insensitively, recorded as written
OPERATOR_TOPS = {("D1", "cell observer", "ainhize"), ("D1", "cell observer", "marta"),
                 ("D2", "cell observer 2", "ainhize"), ("D2", "cell observer 2", "marta")}
NEW_PROJECT = "AE-biomaGUNE-0118"      # the only project this ingest creates
XMIC_MODEL = "Axio Imager.Z2"
XMIC_SOURCE = "collaborator:Charite"
BATCH_CAP = 400 * 10**9                # bytes; big CELL batches are cut here
MFB_RE = re.compile(r"^MFB[_-]([A-Za-z]+)[_-]([^_]+)[_-]([^_]+)[_-]")
NOTE = ("Historical drive ingest 2026 ({label}); project / researcher / operator / subject decided "
        "per file before ingest (tasks/drives_ingest_dryrun_review.md). Claim: {claim}.")


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


def archive_key(drive, archive_relpath):
    """Folder name under _extract\\ for one archive: short, unique, readable."""
    base = archive_relpath.split("\\")[-1]
    h = hashlib.sha1(f"{drive}|{archive_relpath}".encode("utf-8")).hexdigest()[:6]
    return f"{drive}_{h}_{base}"


# ---------------------------------------------------------------------------------------------
# goptical: which ZWSI are already in the AxioScan's own archive
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
# plan
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
    Rule 2 is three-valued -- loose outside the backup, loose backup, archive member -- so a loose
    copy is preferred to an extraction when the rule's own two values tie; `strict` is the rule
    exactly as written (two values), kept to report whether the refinement ever changed a pick."""
    if strict:
        loc = 0 if c["kind"] == "loose" and not c["in_backup"] else 1
    else:
        loc = 0 if c["kind"] == "loose" and not c["in_backup"] else 1 if c["kind"] == "loose" else 2
    return (0 if c["project"] else 1, loc, 0 if c["researcher"] else 1, len(c["path"]),
            0 if c["drive"] == "D1" else 1, c["path"])


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


def cmd_plan(args):
    os.makedirs(args.out, exist_ok=True)
    today = dt.date.today().isoformat()

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
        c["in_backup"] = c["path"].startswith(BACKUP_TOP + "\\")
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
            claim_txt = "A (118 -> 0118; subject HELD until confirmed)"
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
        })

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
        bid = f"B{n:02d}"
        for e in es:
            e["batch"] = bid
        batches.append({"batch": bid, "bucket": b, "instrument": es[0]["instrument"], "files": len(es),
                        "gb": gb(sum(e["size"] for e in es)),
                        "projects": ";".join(sorted({e["project"] for e in es if e["project"]})) or "(none)",
                        "members": sum(1 for e in es if e["kind"] == "member"),
                        "auto_create": "Y" if b == "CELL-0118" else "N",
                        "needs_decision": "reopen closed project" if b.startswith("CELL-closed") else ""})

    # ---- link names: unique per project, against what raw_linked\ already holds ---------------------
    taken = {}
    for e in sorted(expected, key=lambda e: e["original_name"]):
        base = e["original_name"].split("/")[-1]
        stem, ext = os.path.splitext(base)
        name = f"{e['instrument']}_{base}"
        if e["project"]:
            key = e["project"].lower()
            if key not in taken:
                p = projects.get(key)
                taken[key] = existing_links(args.nas, p["folder"]) if p else set()
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

    # ---- write -----------------------------------------------------------------------------------------
    cols = ["batch", "sha256", "size", "instrument", "kind", "drive", "relpath", "archive", "member",
            "original_name", "acquisition_datetime", "czi_stand", "instrument_model", "project",
            "project_id", "project_status", "verdict", "claimed", "researcher", "operator", "subject_id",
            "subject_alias", "subject_animal", "sample_id", "sample_type", "data_source", "link_name",
            "notes", "conflict", "n_copies", "other_copies"]
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
# extract: archive-only canonical copies
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
# farm: one hard-link tree per batch, laid out so original_name == <label>/<source path>
# ---------------------------------------------------------------------------------------------

def farm_source(e):
    if e["kind"] == "loose":
        return staged_path(e["drive"], e["relpath"])
    return os.path.join(EXTRACT, archive_key(e["drive"], e["archive"]), e["member"].replace("/", "\\"))


def farm_target(e):
    return os.path.join(FARM, e["batch"], e["original_name"].replace("/", "\\"))


def cmd_farm(args):
    exp = load_expected(args.out)
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
             "drv_sha256", "drv_claim"]

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
EXTRA_CLOSED = """#
# !! TARGET PROJECT IS CLOSED (folder deleted 2026-07-14). Do NOT run until the coordinator has
# decided to reopen it: Step 12 would otherwise re-create projects/<name>/raw_linked/ alone.
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
             "drv_claim": e["verdict"]} for e in es))
        extra = EXTRA_0118 if b["bucket"] == "CELL-0118" else EXTRA_XMIC if inst == "XMIC" else \
            EXTRA_CLOSED if b["bucket"].startswith("CELL-closed") else ""
        text = YAML.format(
            batch=b["batch"], instrument=inst, files=b["files"], gb=b["gb"], bucket=b["bucket"],
            projects=b["projects"], generated=generated, cases=cases, extra=extra,
            auto_create="true" if b["auto_create"] == "Y" else "false",
            staging=os.path.join(FARM, b["batch"]).replace("\\", "/"),
            model=f'"{XMIC_MODEL}"' if inst == "XMIC" else "discovered.czi_microscope_name",
            data_source=f'"{XMIC_SOURCE}"' if inst == "XMIC" else "internal",
            acp=ACP_0118 if b["auto_create"] == "Y" else "")
        with open(os.path.join(args.config_dir, f"drives_{b['batch']}.yaml"), "w", encoding="utf-8",
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
            continue  # created by the rehearsal itself (0118)
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
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--nas", default=NAS, help="production NAS root, read-only here")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("goptical")
    g.add_argument("--hash", action="store_true")
    sub.add_parser("plan")
    sub.add_parser("extract")
    f = sub.add_parser("farm")
    f.add_argument("--batch", action="append")
    c = sub.add_parser("configs")
    c.add_argument("--config-dir", default=CONFIG_DIR)
    sc = sub.add_parser("scratch")
    sc.add_argument("--root", default=r"D:\projects\gjesus3\scratch_nas")
    sc.add_argument("--batch", action="append")
    args = ap.parse_args()
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    {"goptical": cmd_goptical, "plan": cmd_plan, "extract": cmd_extract, "farm": cmd_farm,
     "configs": cmd_configs, "scratch": cmd_scratch}[args.cmd](args)


if __name__ == "__main__":
    main()
