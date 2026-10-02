#!/usr/bin/env python3
"""nonraw_placement.py -- place the historical drives' NON-RAW material into project folders.

ONE-TIME TOOL for the 2026-09/10 historical-microscopy-drives close-out (branch
feat/drives-nonraw-placement, close-out plan Step 5 items 2/2b/2c). The record of what it did and
why is tasks/drives_nonraw_placement_review.md.

    python tools/drive_staging/nonraw_placement.py plan                 # -> <out>\\placement_manifest.csv + summaries
    python tools/drive_staging/nonraw_placement.py copy [--project N] [--execute]   # dry run unless --execute
    python tools/drive_staging/nonraw_placement.py holding [--execute]  # 2c: unassigned -> staging holding folder
    python tools/drive_staging/nonraw_placement.py worksheet            # 2b: group-level mapping worksheet

DECISIONS IT IMPLEMENTS (Ryan, 2026-10-01/02; close-out plan "Two placement decisions"):
  * Raw (the acquisition / reconstruction) is not this tool's business. Everything else under a
    project claim -- exports, .tif/.tiff, scale-bar copies, figures, analysis, documents, EM (.dm4),
    video -- is COPIED to
        <NAS>\\projects\\<project folder>\\working\\historical_drives\\<drive label>\\<original path>
    where <original path> is the relpath below the drive root. An archive member goes under the
    archive's own relpath with the archive's name turned into a folder `<stem>_<ext>` (e.g.
    `Manon.zip` -> `Manon_zip\\`), then the member path.
  * Excluded: class software / system, the archives that are installers, the personal/admin
    heuristic hits, zero-byte files (counted), and every `czi-raw` (ingested, excluded as
    in-production, or a re-save Ryan said to skip).
  * Other streams' material is never placed here: imaging classes (bruker / volume / nmr) AND every
    file in a directory that holds one (stream B, the drives' DICOM), `LEONE.zip` (stream C).
  * `.lsm` and every file with no claim or a (C) claim -> `holding` (2c, later).
  * (B) `Project-0521` takes the 4 `Antiguo proyecto 0720` members as well (no Project-0720).
  * A target project whose registry status is `closed` -> decision `closed-project`: listed, never
    copied by this tool until the project is reopened (Ryan's case-by-case call).

THE COPY (`copy --execute`), per file: stream the source (staged loose file, or the member read out
of its archive) into `<dest dir>\\.~nonraw-<sha8>.part`, re-read that temp file FROM THE NAS and hash
it, compare with the manifest SHA-256, rename it into place (os.rename: fails if the target exists,
so nothing is ever overwritten), then append the project's provenance.csv row. Re-runnable: a dest
that already holds identical bytes is skipped (its provenance row is still ensured); a dest that
holds DIFFERENT bytes is a collision -- reported, never touched, and the run stops for that project.

Writes nothing under /raw/ or registries/. Reads the staged drives read-only.
"""
import argparse
import collections
import csv
import datetime as dt
import getpass
import hashlib
import io
import os
import random
import re
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))  # tools/ -> `ingest` package

STAGING = r"D:\projects\gjesus3\staging"
ANALYSIS = os.path.join(STAGING, "_analysis")
OUT_DEFAULT = os.path.join(ANALYSIS, "drives-nonraw-placement")
NAS_DEFAULT = r"J:\gjesus3-data"
SEVENZIP = r"C:\Program Files\7-Zip\7z.exe"

DRIVES = {  # catalog code -> (drive label used on the NAS, staged root)
    "D1": ("drive1_FRIO-X6", os.path.join(STAGING, "drive1_FRIO-X6_2322E4A111E7")),
    "D2": ("drive2_MFB-Disco-2", os.path.join(STAGING, "drive2_MFB-Disco-2_2322E4A112BD")),
}
CLAIMS_DRIVE = {"drive1": "D1", "drive2": "D2"}
SUBDIR = ("working", "historical_drives")

IMAGING_CLASSES = {"bruker", "volume", "nmr"}           # stream B
EXCLUDE_CLASSES = {"software": "software", "system": "system-file"}
LEONE = "LEONE.zip"                                     # stream C
INSTALLER_ARCHIVE_RE = re.compile(r"Downloadly|\\Crack\\|(^|\\)ok\.dll\.zip$", re.I)
PROJECT_0521 = "Project-0521"
ANTIGUO_0720_RE = re.compile(r"Antiguo proyecto 0720", re.I)

# Projects Ryan approved on 2026-09-29/10-02 that may not exist yet. The tool creates none of them
# (create_project.py does); it only lets a claim target one before it exists.
APPROVED_NEW = {"AE-biomaGUNE-1116", "AE-biomaGUNE-1420", "AE-biomaGUNE-1520", PROJECT_0521,
                "AE-biomaGUNE-1319"}

NESTED_SEP = "!"  # member "<nested archive>!<inner path>" for archives inside archives

MANIFEST_FIELDS = [
    "row", "drive", "drive_label", "relpath", "archive", "member", "size", "sha256", "class", "ext",
    "flag", "claim_id", "verdict", "researcher", "project_name", "project_id", "project_status",
    "dest_rel", "decision", "reason", "note",
]


# ---------------------------------------------------------------------------------------- helpers

def lp(path):
    """Long-path form for Windows (`\\\\?\\` / `\\\\?\\UNC\\`). Identity elsewhere."""
    if os.name != "nt":
        return path
    path = os.path.abspath(path)
    if path.startswith("\\\\?\\"):
        return path
    if path.startswith("\\\\"):
        return "\\\\?\\UNC\\" + path[2:]
    return "\\\\?\\" + path


def rd(path):
    with io.open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def it(path):
    with io.open(path, encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)


def wcsv(path, fields, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def win(p):
    return p.replace("/", "\\")


def archive_folder_name(archive_name):
    """`Manon.zip` -> `Manon_zip`; `Haizpea_2020-2022.7z` -> `Haizpea_2020-2022_7z`.

    A folder named exactly like the archive (`Manon.zip\\`) reads as a file in Explorer, and the bare
    stem (`Manon\\`) can collide with a real sibling folder of the same name; `<stem>_<ext>` is
    neither, and stays obviously "the contents of that archive"."""
    stem, ext = os.path.splitext(archive_name)
    return f"{stem}_{ext.lstrip('.')}" if ext else f"{stem}_archive"


def source_rel(relpath, archive="", member=""):
    """The path below the drive root as it will appear under historical_drives\\<label>\\."""
    if not archive:
        return win(relpath)
    adir, aname = os.path.split(win(archive))
    if NESTED_SEP in member:  # a member of an archive inside the archive
        nested, inner = member.split(NESTED_SEP, 1)
        ndir, nname = os.path.split(win(nested).strip("\\"))
        mpath = "\\".join(p for p in (ndir, archive_folder_name(nname), win(inner).strip("\\")) if p)
    else:
        mpath = win(member).strip("\\")
    parts = [p for p in (adir, archive_folder_name(aname), mpath) if p]
    return "\\".join(parts)


def dest_rel(project_folder, drive_label, relpath, archive="", member=""):
    """NAS-relative destination (backslashes, no leading slash)."""
    return "\\".join(["projects", project_folder, *SUBDIR, drive_label,
                      source_rel(relpath, archive, member)])


def holding_rel(drive_label, relpath, archive="", member=""):
    return "\\".join(["staging", "historical_drives_unassigned", drive_label,
                      source_rel(relpath, archive, member)])


def is_personal(flag):
    return (flag or "").startswith("personal-admin-heuristic")


def is_zero(flag, size):
    return "zero-byte" in (flag or "") or str(size) == "0"


# --------------------------------------------------------------------------------- the decision

def project_for(verdict, proposed, where):
    """Claim -> project name, or None for holding. `where` is the path (or archive!member) the claim
    applies to; it is only consulted for the 0720-in-0521 fold."""
    if verdict in ("CONFIRMED", "A"):
        return proposed or None
    if verdict == "B":
        return PROJECT_0521  # 0521 itself, and 0720 folded into it (Ryan, 2026-10-02)
    if verdict == "C" and ANTIGUO_0720_RE.search(where or ""):
        return PROJECT_0521
    return None


def decide(rec, ctx):
    """One manifest record -> (decision, reason, project_name or None).

    `rec` keys: drive, relpath, archive, member, class, flag, size, verdict, proposed_project,
    imaging_root (str or None), excluded_reason, derived (dict or None).
    `ctx`: projects (name -> registry row)."""
    cls, flag = rec["class"], rec["flag"]
    where = f"{rec['relpath']}!{rec['member']}" if rec["archive"] else rec["relpath"]
    if rec["archive"] == LEONE or (not rec["archive"] and rec["relpath"] == LEONE):
        return "other-stream", "C: LEONE.zip", None
    if rec.get("special"):  # a per-file decision made by the caller (nested-archive specials)
        return rec["special"]
    if rec.get("derived"):
        d = rec["derived"]
        return "place", f"R3 derivative of {d['parent_acq_ids']} ({d['why']})", d["project"]
    if cls == "czi-raw":
        if rec.get("excluded_reason") == "hidden-dotfile":
            return "raw-oneoff", "hidden dot-file .czi: a real acquisition -> /raw/ (separate config)", None
        why = rec.get("excluded_reason") or ("ingested" if rec.get("ingested") else "czi-raw")
        return "exclude", f"czi-raw ({why})", None
    if cls in EXCLUDE_CLASSES:
        return "exclude", EXCLUDE_CLASSES[cls], None
    if cls == "archive" and INSTALLER_ARCHIVE_RE.search(win(rec["relpath"])):
        return "exclude", "software (installer archive)", None
    if is_personal(flag):
        return "exclude", "personal-admin-heuristic", None
    if is_zero(flag, rec["size"]):
        return "exclude", "zero-byte", None
    if rec.get("from_b") is not None:  # stream B's own non-raw list (nonraw_for_A.csv), its project
        proj = rec["from_b"] or None
        if not proj:
            return "holding", "B->A non-raw, no project", None
        return _project_decision(proj, ctx, "B->A non-raw")
    if rec.get("imaging_root"):
        return "other-stream", f"B: under imaging root ({rec['imaging_root']})", None
    if cls in IMAGING_CLASSES:
        return "other-stream", f"B?: imaging class {cls} OUTSIDE B's roots (listed for B)", None
    if cls == "archive" and not rec["archive"]:
        return "expanded", "archive: its members are decided one by one", None
    if cls == "czi-unreadable":
        return "unclear", "czi-unreadable with bytes: a damaged acquisition or not? (not ingested)", None
    if cls == "lsm":
        return "holding", "lsm -> holding folder (Ryan, 2026-10-02)", None
    proj = project_for(rec["verdict"], rec["proposed_project"], where)
    if not proj:
        why = {"C": "(C) claim", "": "no claim"}.get(rec["verdict"], f"verdict {rec['verdict']}")
        return "holding", why, None
    return _project_decision(proj, ctx, f"claim {rec['verdict']}")


def _project_decision(proj, ctx, why):
    row = ctx["projects"].get(proj)
    if row is None and proj not in APPROVED_NEW:
        return "unclear", f"{why}: targets {proj}, which is neither in the registry nor approved", proj
    if row is not None and (row.get("status") or "").strip().lower() == "closed":
        return "closed-project", f"{proj} is closed: reopen is Ryan's case-by-case call ({why})", proj
    return "place", why, proj


# ----------------------------------------------------------------------------------------- plan

ROOTS_DEFAULT = os.path.join(ANALYSIS, "drives-dicom", "imaging_roots.csv")


def load_imaging_roots(path):
    """Stream B's claimed imaging roots: (drive, archive or '-') -> [(prefix, label)]. Loose prefixes
    use backslashes, member prefixes forward slashes; an empty member prefix is the whole archive."""
    roots = collections.defaultdict(list)
    for r in rd(path):
        roots[(r["drive"], r["archive"] or "-")].append(
            (r["path_prefix"].strip("\\/"), f"{r['kind']}: {r['archive'] if r['archive'] != '-' else ''}"
                                             f"{'!' if r['archive'] != '-' else ''}{r['path_prefix'] or '(whole archive)'}"))
    return roots


def imaging_root(roots, drive, archive, path):
    """The label of the B root covering this loose path (archive '-') or archive member, else None."""
    sep = "\\" if archive == "-" else "/"
    p = path.replace("/", sep) if archive == "-" else path.replace("\\", "/")
    for prefix, label in roots.get((drive, archive), ()):
        if not prefix or p == prefix or p.startswith(prefix + sep):
            return label
    return None


def load_projects(nas):
    rows = rd(os.path.join(nas, "registries", "registry_projects.csv"))
    return {r["name"]: r for r in rows}


def project_folder(proj, projects):
    row = projects.get(proj)
    if row and row.get("folder_location"):
        return row["folder_location"].strip("/").split("/")[-1]
    from ingest.project_naming import folder_name
    return folder_name(proj)


def cmd_plan(args):
    out = args.out
    projects = load_projects(args.nas)
    log = []

    def say(msg):
        print(msg, flush=True)
        log.append(msg)

    say(f"plan {dt.datetime.now():%Y-%m-%d %H:%M}  nas={args.nas}  projects={len(projects)}")
    files = rd(os.path.join(ANALYSIS, "catalog", "files.csv"))
    fclaims = {(CLAIMS_DRIVE[r["drive"]], r["relpath"]): r
               for r in it(os.path.join(ANALYSIS, "codes", "file_claims.csv"))}
    excluded = {r["path"]: r["reason"] for r in it(os.path.join(ANALYSIS, "ingest", "excluded.csv"))}
    prov = os.path.join(args.repo, "tasks", "drives_ingest_provenance.csv")
    ingested_loose, ingested_member = set(), set()
    for r in it(prov):
        if r["archive"]:
            ingested_member.add((r["archive"], r["member"]))
        else:
            ingested_loose.add(r["relpath"])
    derived = {}
    names = {prow["project_id"]: n for n, prow in projects.items()}
    for r in it(os.path.join(ANALYSIS, "ingest", "nonraw_derived.csv")):
        pids = [p for p in re.split(r"[;|, ]+", r["parent_project_ids"]) if p]
        pnames = sorted({names.get(p, p) for p in pids})
        derived[(r["drive"], r["relpath"])] = {
            "why": r["why"], "parent_acq_ids": r["parent_acq_ids"],
            "project": pnames[0] if len(pnames) == 1 else None, "all": pnames}
    for k, d in derived.items():
        if d["project"] is None:
            say(f"!! derivative with {len(d['all'])} parent projects: {k}")

    # stream B's imaging roots (drives-dicom/imaging_roots.csv), in place of the directory rule
    roots = load_imaging_roots(args.roots)
    say(f"imaging roots: {sum(len(v) for v in roots.values())} from {args.roots}")
    fromb = {}  # stream B's non-raw list: (drive, archive or '-', path) -> project ('' = none)
    if os.path.exists(args.from_b):
        for r in it(args.from_b):
            fromb[(r["drive"], r["archive"] or "-", r["path"])] = r["project"]
    say(f"B->A non-raw rows: {len(fromb)} from {args.from_b}")
    nested_rows = rd(args.nested) if os.path.exists(args.nested) else []
    nested_archives = {(r["drive"], r["archive"], r["nested"]) for r in nested_rows}
    say(f"nested-archive members: {len(nested_rows)} in {len(nested_archives)} nested archives")

    rows = []

    def add(base, rec):
        dec, reason, proj = decide(rec, {"projects": projects})
        r = dict(base)
        r.update(decision=dec, reason=reason)
        if proj:
            prow = projects.get(proj)
            r["project_name"] = proj
            r["project_id"] = prow["project_id"] if prow else "NEW"
            r["project_status"] = prow["status"] if prow else "approved-new"
        if dec in ("place", "closed-project") and proj:
            r["dest_rel"] = dest_rel(project_folder(proj, projects), base["drive_label"],
                                     base["relpath"], base["archive"], base["member"])
        elif dec == "holding":
            r["dest_rel"] = holding_rel(base["drive_label"], base["relpath"], base["archive"],
                                        base["member"])
        rows.append(r)

    archives = {}
    for f in files:
        drive = f["drive"]
        c = fclaims.get((drive, f["relpath"]), {})
        base = {"drive": drive, "drive_label": DRIVES[drive][0], "relpath": f["relpath"],
                "archive": "", "member": "", "size": f["size"], "sha256": f["sha256"],
                "class": f["class"], "ext": f["ext"], "flag": f["flag"],
                "claim_id": c.get("claim_id", ""), "verdict": c.get("verdict", ""),
                "researcher": c.get("researcher", "")}
        rec = dict(base, proposed_project=c.get("proposed_project", ""),
                   imaging_root=imaging_root(roots, drive, "-", f["relpath"]),
                   excluded_reason=excluded.get(f["relpath"]),
                   ingested=f["relpath"] in ingested_loose,
                   derived=derived.get((drive, f["relpath"])),
                   from_b=fromb.get((drive, "-", f["relpath"])))
        add(base, rec)
        if f["class"] == "archive":
            archives[(drive, f["relpath"])] = rows[-1]
    say(f"loose files: {len(rows)}")

    # archive members: claims per member where the claims pass produced them, else the archive's own
    mclaims = {}
    for r in it(os.path.join(ANALYSIS, "codes", "archive_member_claims.csv")):
        mclaims[(CLAIMS_DRIVE[r["drive"]], r["archive_relpath"], r["member"])] = r
    say(f"member claims: {len(mclaims)}")
    members = []
    leone = 0
    for m in it(os.path.join(ANALYSIS, "catalog", "archive_members.csv")):
        if m["archive_relpath"] == LEONE:
            leone += 1  # counted, not listed: 671k members of stream C
            continue
        if m["member"].endswith("/"):
            continue
        members.append(m)
    say(f"archive members (excl. LEONE): {len(members)}")
    for m in members:
        drive = m["drive"]
        arch = archives.get((drive, m["archive_relpath"]))
        if arch is None:
            say(f"!! member of an archive not in files.csv: {drive} {m['archive_relpath']}")
            continue
        mc = mclaims.get((drive, m["archive_relpath"], m["member"]))
        if mc is None and arch["verdict"] == "ARCHIVE":  # multi-claim archive: no row = no claim
            mc = {"researcher": arch["researcher"]}
        if mc is None:  # inherit the archive file's own claim
            mc = {"claim_id": arch["claim_id"], "verdict": arch["verdict"],
                  "researcher": arch["researcher"],
                  "proposed_project": fclaims.get((drive, m["archive_relpath"]), {}).get("proposed_project", "")}
        base = {"drive": drive, "drive_label": DRIVES[drive][0], "relpath": m["archive_relpath"],
                "archive": m["archive_relpath"], "member": m["member"], "size": m["size"],
                "sha256": m["sha256"], "class": m["class"], "ext": m["ext"], "flag": m["flag"],
                "claim_id": mc.get("claim_id", ""), "verdict": mc.get("verdict", ""),
                "researcher": mc.get("researcher", "")}
        installer = bool(INSTALLER_ARCHIVE_RE.search(win(m["archive_relpath"])))
        rec = dict(base, proposed_project=mc.get("proposed_project", ""),
                   imaging_root=imaging_root(roots, drive, m["archive_relpath"], m["member"]),
                   excluded_reason=None,
                   ingested=(m["archive_relpath"], m["member"]) in ingested_member,
                   derived=None,
                   from_b=fromb.get((drive, m["archive_relpath"], m["member"])))
        if (drive, m["archive_relpath"], m["member"]) in nested_archives:
            rec["special"] = ("expanded", "nested archive: its members are decided one by one", None)
        if installer:
            rows.append(dict(base, decision="exclude", reason="software (inside an installer archive)"))
            continue
        if arch["decision"] == "other-stream" and rec["from_b"] is None:  # archive in B's territory
            rows.append(dict(base, decision="other-stream", reason=f"{arch['reason']} (its archive)"))
            continue
        add(base, rec)
    say(f"LEONE members counted, not listed: {leone}")

    # members of archives inside archives (cmd_nested): claim = the outer archive's; a few specials
    for n in nested_rows:
        drive = n["drive"]
        arch = archives[(drive, n["archive"])]
        member = n["nested"] + NESTED_SEP + n["inner"]
        base = {"drive": drive, "drive_label": DRIVES[drive][0], "relpath": n["archive"],
                "archive": n["archive"], "member": member, "size": n["size"], "sha256": n["sha256"],
                "class": n["class"], "ext": n["ext"], "flag": n["flag"],
                "claim_id": arch["claim_id"], "verdict": "" if arch["verdict"] == "ARCHIVE" else arch["verdict"],
                "researcher": arch["researcher"]}
        rec = dict(base, proposed_project=fclaims.get((drive, n["archive"]), {}).get("proposed_project", ""),
                   imaging_root=imaging_root(roots, drive, n["archive"], os.path.splitext(n["nested"])[0] + "/x"),
                   excluded_reason=None, ingested=False, derived=None, from_b=None)
        rec["special"] = nested_special(n, prod_sha=None)
        add(base, rec)

    # Simu_2_V_XYZ.zip and other unreadable archives: nothing listed -> the archive itself is unclear
    for a in rd(os.path.join(ANALYSIS, "catalog", "archives.csv")):
        if a["status"] not in ("ok",) and not INSTALLER_ARCHIVE_RE.search(win(a["archive_relpath"])):
            for r in rows:
                if not r["archive"] and r["relpath"] == a["archive_relpath"] and r["decision"] == "expanded":
                    r["decision"], r["reason"] = "unclear", f"archive could not be listed ({a['status']} {a['err']})"

    for i, r in enumerate(rows, 1):
        r["row"] = i
    annotate_duplicates(rows, say)
    check_nas(rows, args.nas, projects, say)
    wcsv(os.path.join(out, "placement_manifest.csv"), MANIFEST_FIELDS, rows)
    write_summaries(rows, out, args.repo, say, leone)
    with io.open(os.path.join(out, "plan.log"), "a", encoding="utf-8") as f:
        f.write("\n".join(log) + "\n\n")


NESTED_PERSONAL_RE = re.compile(r"Meals cost original documents\.zip$", re.I)  # meal receipts (B, 2026-10-02)


def nested_special(n, prod_sha=None):
    """Per-file decisions for nested-archive members that the general rules would get wrong."""
    if NESTED_PERSONAL_RE.search(n["nested"]):
        return ("exclude", "personal-admin (meal receipts archive)", None)
    if n["class"] == "czi-raw":
        return ("raw-oneoff", "czi-raw inside a nested archive: never seen by the .czi ingest -> /raw/ "
                              "one-off (dedup against production first)", None)
    if n["ext"].lower() == ".svs":
        return ("unclear", "Aperio .svs whole-slide scan: instrument not onboarded (question for Ryan; "
                           "default holding unless under a claim)", None)
    return None


def annotate_duplicates(rows, say):
    """Same content placed into >1 project -> note on each; redundant copies within one project are
    placed anyway (path structure over bytes) and only counted."""
    by_sha = collections.defaultdict(list)
    for r in rows:
        if r["decision"] in ("place", "closed-project") and r["sha256"]:
            by_sha[r["sha256"]].append(r)
    cross = 0
    for sha, rs in by_sha.items():
        projs = sorted({r["project_name"] for r in rs})
        if len(projs) > 1:
            cross += 1
            for r in rs:
                r["note"] = (r.get("note", "") + f" same-bytes-in:{'|'.join(projs)}").strip()
    say(f"contents placed into more than one project: {cross}")


def check_nas(rows, nas, projects, say):
    """Read-only. Does any destination already exist? Only projects whose historical_drives folder
    exists can collide, so stat those destinations only."""
    roots = {}
    for r in rows:
        if r["decision"] != "place":
            continue
        proj = r["project_name"]
        if proj not in roots:
            root = os.path.join(nas, "projects", project_folder(proj, projects), *SUBDIR)
            roots[proj] = os.path.isdir(lp(root))
        if roots[proj]:
            p = lp(os.path.join(nas, r["dest_rel"]))
            if os.path.exists(p):
                r["note"] = (r.get("note", "") + " dest-exists").strip()
    say(f"projects with an existing historical_drives folder: {sorted(p for p, e in roots.items() if e)}")
    missing = sorted(p for p in roots if not os.path.isdir(lp(os.path.join(nas, "projects", project_folder(p, projects)))))
    say(f"target project folders missing on the NAS: {missing}")


def gb(n):
    return f"{n / 1e9:.2f}"


def write_summaries(rows, out, repo, say, leone):
    by_dec = collections.defaultdict(lambda: [0, 0])
    by_reason = collections.defaultdict(lambda: [0, 0])
    by_proj = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
    by_cls = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0]))
    for r in rows:
        n = int(r["size"] or 0)
        for d, k in ((by_dec, r["decision"]), (by_reason, (r["decision"], r["reason"]))):
            d[k][0] += 1
            d[k][1] += n
        by_cls[r["class"]][r["decision"]][0] += 1
        by_cls[r["class"]][r["decision"]][1] += n
        if r["decision"] in ("place", "closed-project"):
            key = (r["project_name"], r["project_id"], r["project_status"], r["decision"])
            by_proj[key][r["class"]][0] += 1
            by_proj[key][r["class"]][1] += n
    say("\nBY DECISION")
    for k, (c, n) in sorted(by_dec.items()):
        say(f"  {k:16s} {c:8d} files {gb(n):>10s} GB")
    say(f"  (+ {leone} LEONE.zip members, stream C, not listed)")
    say("\nBY DECISION / REASON")
    for (d, why), (c, n) in sorted(by_reason.items()):
        say(f"  {d:16s} {why[:70]:70s} {c:8d} {gb(n):>9s} GB")
    prow = []
    for (proj, pid, st, dec), classes in sorted(by_proj.items()):
        c = sum(v[0] for v in classes.values())
        n = sum(v[1] for v in classes.values())
        prow.append({"project_name": proj, "project_id": pid, "project_status": st, "decision": dec,
                     "files": c, "bytes": n, "gb": gb(n),
                     "by_class": "; ".join(f"{k}:{v[0]}" for k, v in sorted(classes.items()))})
    wcsv(os.path.join(out, "per_project_summary.csv"),
         ["project_name", "project_id", "project_status", "decision", "files", "bytes", "gb", "by_class"], prow)
    wcsv(os.path.join(repo, "tasks", "drives_nonraw_placement_per_project.csv"),
         ["project_name", "project_id", "project_status", "decision", "files", "bytes", "gb", "by_class"], prow)
    say("\nPER PROJECT (place / closed-project)")
    for p in prow:
        say(f"  {p['project_id']:9s} {p['project_name']:28s} {p['project_status']:12s} {p['decision']:14s} {p['files']:6d} {p['gb']:>8s} GB")
    crow = []
    for cls, decs in sorted(by_cls.items()):
        for dec, (c, n) in sorted(decs.items()):
            crow.append({"class": cls, "decision": dec, "files": c, "bytes": n, "gb": gb(n)})
    wcsv(os.path.join(out, "per_class_summary.csv"), ["class", "decision", "files", "bytes", "gb"], crow)


# ----------------------------------------------------------------------------------------- copy

class Collision(Exception):
    pass


def sha256_file(path, bufsize=8 << 20):
    h = hashlib.sha256()
    with open(lp(path), "rb") as f:
        while True:
            b = f.read(bufsize)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def staged_path(r):
    return os.path.join(DRIVES[r["drive"]][1], "files", win(r["relpath"]))


class MemberSource:
    """Read archive members one at a time. zip: zipfile. 7z/rar: one 7-Zip call per archive with a
    list file, extracting ONLY the listed members into a scratch folder on D: (deleted after)."""

    def __init__(self, scratch):
        self.scratch = scratch
        self._zips = {}
        self._extracted = {}

    def open(self, r):
        ap = staged_path(r)
        if ap.lower().endswith(".zip"):
            z = self._zips.get(ap)
            if z is None:
                z = self._zips[ap] = zipfile.ZipFile(lp(ap))
            if NESTED_SEP in r["member"]:
                nested, inner = r["member"].split(NESTED_SEP, 1)
                key = (ap, nested)
                nz = self._zips.get(key)
                if nz is None:
                    nz = self._zips[key] = zipfile.ZipFile(z.open(nested))
                return nz.open(inner)
            return z.open(r["member"])
        root = self._extracted.get(ap)
        if root is None:
            raise RuntimeError(f"7z members of {ap} not pre-extracted (call prepare_7z)")
        return open(lp(os.path.join(root, win(r["member"]))), "rb")

    def prepare_7z(self, archive_path, members):
        tag = hashlib.sha1(archive_path.encode("utf-8")).hexdigest()[:8]
        root = os.path.join(self.scratch, f"x7z_{tag}")
        os.makedirs(lp(root), exist_ok=True)
        lst = os.path.join(self.scratch, f"x7z_{tag}.txt")
        with io.open(lst, "w", encoding="utf-8") as f:
            f.write("\n".join(members) + "\n")
        subprocess.run([SEVENZIP, "x", "-y", "-scsUTF-8", f"-o{root}", archive_path, f"@{lst}"],
                       check=True, stdout=subprocess.DEVNULL)
        self._extracted[archive_path] = root

    def close(self):
        for z in self._zips.values():
            z.close()


def copy_one(r, nas, members, bufsize=8 << 20):
    """-> 'copied' | 'skipped-identical'. Raises Collision on different bytes at the destination."""
    dest = os.path.join(nas, r["dest_rel"])
    if os.path.exists(lp(dest)):
        if sha256_file(dest) == r["sha256"]:
            return "skipped-identical"
        raise Collision(dest)
    ddir = os.path.dirname(dest)
    os.makedirs(lp(ddir), exist_ok=True)
    tmp = os.path.join(ddir, f".~nonraw-{r['sha256'][:8]}.part")
    src = members.open(r) if r["archive"] else open(lp(staged_path(r)), "rb")
    h = hashlib.sha256()
    try:
        with src, open(lp(tmp), "wb") as out:
            while True:
                b = src.read(bufsize)
                if not b:
                    break
                h.update(b)
                out.write(b)
            out.flush()
            os.fsync(out.fileno())
        if h.hexdigest() != r["sha256"]:
            raise RuntimeError(f"source bytes do not match the manifest: {r['relpath']} {r['member']}")
        if sha256_file(tmp) != r["sha256"]:
            raise RuntimeError(f"NAS re-hash mismatch after copy: {dest}")
        os.rename(lp(tmp), lp(dest))  # fails if dest appeared meanwhile: never overwrites
    finally:
        if os.path.exists(lp(tmp)):
            os.remove(lp(tmp))
    return "copied"


def prov_entry(r, run_id, by, today):
    from ingest import provenance
    proj_root = "\\".join(r["dest_rel"].split("\\")[:2])
    out_rel = r["dest_rel"][len(proj_root) + 1:].replace("\\", "/")
    src = f"{r['drive_label']}/{r['relpath'].replace(chr(92), '/')}"
    if r["archive"]:
        src += f"!{r['member']}"
    refs = src
    m = re.search(r"R3 derivative of (\S+)", r["reason"])
    if m:
        refs = f"{m.group(1)}; {src}"
    return {"output_path": out_rel, "output_name": out_rel.split("/")[-1],
            "file_type": os.path.splitext(out_rel)[1] or "file", "date_created": today,
            "creator": by, "input_refs": refs,
            "process_description": (
                "Copied by nonraw_placement.py from the historical operator drive "
                f"{r['drive_label']} (staged 2026-09-22/28): non-raw project material "
                f"(class {r['class']}; {r['reason']}). Byte-verified against the drive manifest."),
            "software_version": provenance.software_version_string("nonraw_placement.py"),
            "parameters_ref": run_id, "lab_notebook_ref": "",
            "notes": f"sha256:{r['sha256']}" + (f"; claim {r['claim_id']}" if r["claim_id"] else "")}


def append_provenance(prov_path, entries):
    """Batched append: one lock, one read of the existing file, many rows. Idempotent on
    output_path, same contract as ingest.provenance.append_entry (which re-reads the whole file per
    row -- too slow over SMB for thousands of rows)."""
    from ingest import csv_safe, locking, provenance
    if not entries:
        return 0
    with locking.registry_lock(os.path.dirname(prov_path)):
        existing = provenance._read_rows(prov_path)
        have = {(e.get("output_path") or "").strip() for e in existing}
        n = 0
        for e in existing:
            fid = e.get("file_id") or ""
            if fid.startswith("FILE-") and fid[5:].isdigit():
                n = max(n, int(fid[5:]))
        todo = [e for e in entries if e["output_path"] not in have]
        if not todo:
            return 0
        file_exists = os.path.exists(prov_path) and os.path.getsize(prov_path) > 0
        csv_safe.ensure_trailing_newline(prov_path)
        with open(prov_path, "a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=provenance.PROVENANCE_HEADERS, extrasaction="ignore")
            if not file_exists:
                w.writeheader()
            seen = set()
            for e in todo:
                if e["output_path"] in seen:
                    continue
                seen.add(e["output_path"])
                n += 1
                e = dict(e, file_id=f"FILE-{n:04d}")
                w.writerow({k: e.get(k, "") for k in provenance.PROVENANCE_HEADERS})
        return len(seen)


def load_manifest(path):
    return rd(path)


def cmd_copy(args):
    rows = [r for r in load_manifest(args.manifest) if r["decision"] == "place"]
    if args.project:
        rows = [r for r in rows if r["project_name"] in args.project]
    projects = load_projects(args.nas)
    by_proj = collections.defaultdict(list)
    for r in rows:
        by_proj[r["project_name"]].append(r)
    run_id = f"NONRAW-{dt.datetime.now():%Y%m%d-%H%M%S}"
    print(f"{run_id} {'EXECUTE' if args.execute else 'DRY RUN'}: {len(rows)} files, "
          f"{gb(sum(int(r['size']) for r in rows))} GB, {len(by_proj)} projects", flush=True)
    missing = [p for p in by_proj if not os.path.isdir(lp(os.path.join(
        args.nas, "projects", project_folder(p, projects))))]
    if missing:
        print(f"project folders missing (create them first): {missing}")
        if args.execute:
            return 2
    log_path = os.path.join(args.out, f"copy_{run_id}.csv")
    if not args.execute:
        long_paths = sum(1 for r in rows if len("\\\\GJESUS3\\gjesus3\\" + r["dest_rel"]) > 259)
        exists = 0
        for p, rs in by_proj.items():
            root = os.path.join(args.nas, "projects", project_folder(p, projects), *SUBDIR)
            if os.path.isdir(lp(root)):
                exists += sum(1 for r in rs if os.path.exists(lp(os.path.join(args.nas, r["dest_rel"]))))
            print(f"  {p:28s} {len(rs):6d} files {gb(sum(int(r['size']) for r in rs)):>8s} GB"
                  f"  -> {os.path.join('projects', project_folder(p, projects), *SUBDIR)}")
        print(f"destinations already present: {exists}; UNC paths over 259 chars: {long_paths}")
        return 0
    by = args.by
    today = dt.date.today().isoformat()
    members = MemberSource(args.scratch)
    for ap, mems in sorted(_sevenzip_members(rows).items()):
        print(f"pre-extracting {len(mems)} members of {ap}", flush=True)
        members.prepare_7z(ap, mems)
    stats = collections.Counter()
    with io.open(log_path, "w", encoding="utf-8", newline="") as lf:
        lw = csv.writer(lf)
        lw.writerow(["row", "project_name", "dest_rel", "sha256", "size", "result"])
        for proj, rs in sorted(by_proj.items()):
            prov_path = os.path.join(args.nas, "projects", project_folder(proj, projects), "provenance.csv")
            pending = []
            for i, r in enumerate(rs, 1):
                try:
                    res = copy_one(r, args.nas, members)
                except Collision as e:
                    res = "COLLISION"
                    print(f"  COLLISION (different bytes, untouched): {e}", flush=True)
                lw.writerow([r["row"], proj, r["dest_rel"], r["sha256"], r["size"], res])
                stats[res] += 1
                if res != "COLLISION":
                    pending.append(prov_entry(r, run_id, by, today))
                if len(pending) >= 200:
                    append_provenance(prov_path, pending)
                    pending = []
                if i % 500 == 0:
                    lf.flush()
                    print(f"  {proj}: {i}/{len(rs)} {dict(stats)}", flush=True)
            append_provenance(prov_path, pending)
            print(f"  {proj}: done {len(rs)}", flush=True)
    members.close()
    print(f"{run_id} finished: {dict(stats)}  log: {log_path}")
    return 1 if stats["COLLISION"] else 0


def _sevenzip_members(rows):
    out = collections.defaultdict(list)
    for r in rows:
        if r["archive"] and not r["archive"].lower().endswith(".zip"):
            out[staged_path(r)].append(r["member"])
    return out


def cmd_verify(args):
    """Count/bytes per project from the NAS + a random re-hash sample."""
    rows = [r for r in load_manifest(args.manifest) if r["decision"] == "place"]
    if args.project:
        rows = [r for r in rows if r["project_name"] in args.project]
    per = collections.defaultdict(lambda: [0, 0, 0, 0])
    for r in rows:
        p = per[r["project_name"]]
        p[0] += 1
        p[1] += int(r["size"])
        d = lp(os.path.join(args.nas, r["dest_rel"]))
        if os.path.exists(d):
            p[2] += 1
            p[3] += os.path.getsize(d)
    bad = 0
    for k, (c, n, c2, n2) in sorted(per.items()):
        ok = c == c2 and n == n2
        bad += not ok
        print(f"  {'OK ' if ok else 'BAD'} {k:28s} manifest {c:6d}/{n} nas {c2:6d}/{n2}")
    random.seed(args.seed)
    sample = random.sample(rows, max(1, int(len(rows) * args.sample))) if rows else []
    mism = [r for r in sample if sha256_file(os.path.join(args.nas, r["dest_rel"])) != r["sha256"]]
    print(f"re-hash sample: {len(sample)} files, {len(mism)} mismatches")
    return 1 if bad or mism else 0


# -------------------------------------------------------------------------------------- holding

README_TXT = """\
Historical operator drives -- unassigned material
=================================================

What this is
  Files from two operator external drives that were staged on 2026-09-22/28:
    drive1_FRIO-X6       (serial 2322E4A111E7)
    drive2_MFB-Disco-2   (serial 2322E4A112BD)
  The folders below keep the drives' own directory structure, so a folder name may
  tell you which study or person a file came from.

Why it is here and not in gjesus3
  These files are NOT part of the gjesus3 archive. They are not raw data (the raw
  acquisitions from these drives were ingested into gjesus3 separately), and they
  have not been assigned to a project.

  Left out on purpose: installed software, system files, and personal or
  administrative documents.

The originals
  The originals remain on the owners' external drives.

If you need something placed in a project
  Ask the Data Office. Tell us the file or folder and the project it belongs to.

manifest.csv lists every file here: relative path, size and SHA-256 (taken from
the drive manifests when the drives were staged).
"""


def cmd_holding(args):
    rows = [r for r in load_manifest(args.manifest) if r["decision"] == "holding"]
    root = os.path.join(args.nas, "staging", "historical_drives_unassigned")
    n = sum(int(r["size"]) for r in rows)
    print(f"{'EXECUTE' if args.execute else 'DRY RUN'}: {len(rows)} files, {gb(n)} GB -> {root}")
    by = collections.Counter((r["drive_label"], r["class"]) for r in rows)
    for k, c in sorted(by.items()):
        print(f"  {k[0]:20s} {k[1]:16s} {c:7d}")
    members_n = sum(1 for r in rows if r["archive"])
    print(f"  of which archive members: {members_n}")
    print(f"  UNC paths over 259 chars: "
          f"{sum(1 for r in rows if len(chr(92) * 2 + 'GJESUS3' + chr(92) + 'gjesus3' + chr(92) + r['dest_rel']) > 259)}")
    print(f"  existing holding folder: {os.path.isdir(lp(root))}")
    man = [{"relative_path": r["dest_rel"].split("\\", 2)[2], "size": r["size"], "sha256": r["sha256"]}
           for r in rows]
    wcsv(os.path.join(args.out, "holding_manifest_preview.csv"), ["relative_path", "size", "sha256"], man)
    with io.open(os.path.join(args.out, "holding_README_preview.txt"), "w", encoding="utf-8", newline="\r\n") as f:
        f.write(README_TXT)
    if not args.execute:
        print(f"previews: {args.out}\\holding_manifest_preview.csv, holding_README_preview.txt")
        return 0
    members = MemberSource(args.scratch)
    for ap, mems in sorted(_sevenzip_members(rows).items()):
        members.prepare_7z(ap, mems)
    stats = collections.Counter()
    for r in rows:
        try:
            stats[copy_one(r, args.nas, members)] += 1
        except Collision as e:
            stats["COLLISION"] += 1
            print(f"  COLLISION (untouched): {e}")
    members.close()
    os.makedirs(lp(root), exist_ok=True)
    with io.open(lp(os.path.join(root, "README.txt")), "w", encoding="utf-8", newline="\r\n") as f:
        f.write(README_TXT)
    wcsv(os.path.join(root, "manifest.csv"), ["relative_path", "size", "sha256"], man)
    print(dict(stats))
    return 1 if stats["COLLISION"] else 0


# --------------------------------------------------------------------------------------- nested

NESTED_FIELDS = ["drive", "archive", "nested", "inner", "size", "sha256", "class", "ext", "flag",
                 "czi_instrument", "czi_rule", "czi_acq_datetime", "czi_stand", "err"]
NESTED_SKIP_OUTER = {LEONE, "Cardiac MRI.zip"}  # streams C and B list their own


def cmd_nested(args):
    """The catalog never opened archives INSIDE archives. List, hash and classify every nested
    archive's members (outside LEONE.zip and Cardiac MRI.zip) with the catalog's own rules: class
    from catalog.path_class, `.czi` refined from its metadata (catalog.czi_class) and fingerprinted
    against tools/reference/microscopy_instruments.yaml. -> <out>\\nested_members.csv"""
    import catalog as C
    ref = C.load_instruments()
    nested = [m for m in it(os.path.join(ANALYSIS, "catalog", "archive_members.csv"))
              if m["class"] == "archive" and m["archive_relpath"] not in NESTED_SKIP_OUTER]
    print(f"nested archives: {len(nested)}", flush=True)
    out, tally = [], collections.Counter()
    for m in nested:
        outer = os.path.join(DRIVES[m["drive"]][1], "files", win(m["archive_relpath"]))
        if not outer.lower().endswith(".zip") or not m["member"].lower().endswith(".zip"):
            print(f"  !! not zip-in-zip, not listed: {m['archive_relpath']} ! {m['member']}")
            tally["not-zip"] += 1
            continue
        with zipfile.ZipFile(lp(outer)) as oz, oz.open(m["member"]) as nf, zipfile.ZipFile(nf) as iz:
            infos = [i for i in iz.infolist() if not i.is_dir()]
            print(f"  {m['archive_relpath']} ! {m['member']}: {len(infos)} members", flush=True)
            for zi in infos:
                rel = m["member"].replace("/", "\\") + "\\" + zi.filename.replace("/", "\\")
                cls = C.path_class(zi.filename)
                want = cls == "czi"
                row = {"drive": m["drive"], "archive": m["archive_relpath"], "nested": m["member"],
                       "inner": zi.filename, "size": zi.file_size, "ext": C.file_ext(zi.filename)}
                try:
                    with iz.open(zi) as f:
                        sha, nb, _dm, czi = C.stream_hash(f, want)
                    row["sha256"] = sha
                    if nb != zi.file_size:
                        row["err"] = f"size-mismatch:{nb}"
                    if want:
                        p = C.czi_summary(C.czi_from_bytes(*czi), ref) or {"ok": False}
                        cls = C.czi_class(p) if "ok" in p else "czi-unreadable"
                        if p.get("ok"):
                            row.update(czi_instrument=p.get("instrument", ""), czi_rule=p.get("rule", ""),
                                       czi_acq_datetime=p.get("acq_dt", ""), czi_stand=p.get("stand", ""))
                except Exception as e:  # counted, never swallowed
                    row["err"] = f"{type(e).__name__}:{e}"[:160]
                    tally["error"] += 1
                hits = C.personal_hit(rel)
                flags = []
                if zi.file_size == 0:
                    flags.append("zero-byte")
                if hits:
                    flags.insert(0, "personal-admin-heuristic:" + "+".join(hits))
                row.update({"class": cls, "flag": ";".join(flags)})
                tally[cls] += 1
                out.append(row)
    wcsv(os.path.join(args.out, "nested_members.csv"), NESTED_FIELDS, out)
    print(f"nested members: {len(out)}  {dict(tally)}")
    czi = [r for r in out if r["ext"] == ".czi"]
    print(f".czi inside nested archives: {len(czi)}")
    for r in czi:
        print(f"  {r['nested'][-60:]} ! {r['inner']}  {r['class']} {r['czi_instrument']} {r['czi_acq_datetime']}")
    return 1 if tally["error"] else 0


# ------------------------------------------------------------------------------------ worksheet

def series_of(relpath, researcher):
    """The `(researcher, series)` group key of project_claims.py (commit e912d79), reproduced so a
    file can be joined to its row of noclaim_groups.csv: series = the first folder below the
    researcher's folder; inside the Toshiba backup, two levels below its root; else the first two
    folders of the path."""
    parts = relpath.split("\\")
    who = researcher or ""
    pos = None
    for i, p in enumerate(parts[:-1]):
        if who and (p.lower() == who.lower() or p.lower().startswith(who.lower())):
            pos = i
    if pos is not None:
        return parts[pos + 1] if pos + 1 < len(parts) - 1 else "(loose files in the person folder)"
    if parts[0].startswith("2025-10-02"):
        return "\\".join(parts[1:3]) if len(parts) > 3 else parts[1] if len(parts) > 2 else "(backup root)"
    return "\\".join(parts[:2]) if len(parts) > 2 else parts[0] if len(parts) > 1 else "(drive root)"


WORKSHEET_FIELDS = ["group", "drive", "researcher", "series", "kind", "nonraw_files", "nonraw_gb",
                    "raw_acqs_blank_project", "date_min", "date_max", "example_1", "example_2",
                    "example_3", "acq_ids", "project", "note_for_ryan"]


def cmd_worksheet(args):
    """2b: one row per no-claim group (noclaim_groups.csv) plus one per (C)-claim group, with the
    holding-bound non-raw files and the blank-project raw acquisitions it would map."""
    rows = load_manifest(args.manifest)
    groups = {}
    for g in it(os.path.join(ANALYSIS, "codes", "noclaim_groups.csv")):
        d = CLAIMS_DRIVE[g["drive"]]
        groups[(d, g["researcher"], g["series"])] = {
            "drive": d, "researcher": g["researcher"], "series": g["series"], "kind": "no claim",
            "files": [], "bytes": 0, "acqs": [], "dates": [g["date_min"], g["date_max"]]}

    def grp(drive, researcher, relpath, verdict, claim_id):
        if verdict == "C":
            key = (drive, researcher, f"(C) {claim_id}")
            kind = "(C) claim"
        else:
            key = (drive, researcher, series_of(relpath, researcher))
            kind = "no claim"
        if key not in groups:
            groups[key] = {"drive": drive, "researcher": researcher, "series": key[2], "kind": kind,
                           "files": [], "bytes": 0, "acqs": [], "dates": []}
        return groups[key]

    for r in rows:
        if r["decision"] != "holding" or r["class"] == "lsm":  # .lsm: holding by decision, not mapped
            continue
        g = grp(r["drive"], r["researcher"], r["relpath"], r["verdict"], r["claim_id"])
        g["files"].append(r["member"] or r["relpath"])
        g["bytes"] += int(r["size"])
    for a in it(os.path.join(args.repo, "tasks", "drives_blank_project_list.csv")):
        rel = a["archive"] or a["relpath"]
        verdict = a["verdict"] if a["verdict"] == "C" else ""
        g = grp(a["drive"], a["researcher"], rel, verdict, a["claim_id"])
        g["acqs"].append(a["acq_id"])
        g["dates"].append(a["acquisition_date"])
    out = []
    for (d, who, series), g in groups.items():
        if not g["files"] and not g["acqs"]:
            continue
        ex = sorted(set(os.path.basename(f.replace("/", "\\")) for f in g["files"]))[:3]
        dates = sorted(x for x in g["dates"] if x)
        out.append({"drive": DRIVES[d][0], "researcher": who, "series": series, "kind": g["kind"],
                    "nonraw_files": len(g["files"]), "nonraw_gb": gb(g["bytes"]),
                    "raw_acqs_blank_project": len(g["acqs"]),
                    "date_min": dates[0] if dates else "", "date_max": dates[-1] if dates else "",
                    "example_1": ex[0] if len(ex) > 0 else "", "example_2": ex[1] if len(ex) > 1 else "",
                    "example_3": ex[2] if len(ex) > 2 else "",
                    "acq_ids": ";".join(sorted(g["acqs"])) if len(g["acqs"]) <= 25 else
                               f"{len(g['acqs'])} ACQ-IDs: {min(g['acqs'])} .. {max(g['acqs'])} (full list: drives_blank_project_list.csv)",
                    "project": "", "note_for_ryan": "", "_bytes": g["bytes"]})
    out.sort(key=lambda x: (-x["_bytes"], -x["raw_acqs_blank_project"]))
    for i, x in enumerate(out, 1):
        x["group"] = f"G{i:03d}"
    path = os.path.join(args.repo, "tasks", "drives_nonraw_mapping_worksheet.csv")
    wcsv(path, WORKSHEET_FIELDS, out)
    print(f"worksheet: {len(out)} groups -> {path}")
    print(f"  non-raw files {sum(x['nonraw_files'] for x in out)}, "
          f"{gb(sum(x['_bytes'] for x in out))} GB; blank raw acqs {sum(x['raw_acqs_blank_project'] for x in out)}")
    return 0


# -------------------------------------------------------------------------------------- dotfile

DOTFILE_REL = r"Cell observer\Laura\Cell observer\Interaccion-LS-SPN\.LS-SPN-20x-8.czi"
DOTFILE_SHA = "59060c3804e666d672c49595497914599c063116cb79b2c75bb8745af435225e"
DOTFILE_FARM = r"D:\projects\gjesus3\scratch_drives-nonraw-placement\farm_dotfile"


def cmd_dotfile_farm(args):
    """Hard-link the hidden dot-file under a non-dot name into a one-file farm (same volume, no
    bytes copied) for tools/configs/drives_2026-10_dotfile/drives_dotfile.yaml."""
    src = os.path.join(DRIVES["D1"][1], "files", DOTFILE_REL)
    d, name = os.path.split(DOTFILE_REL)
    dst = os.path.join(DOTFILE_FARM, DRIVES["D1"][0], d, name.lstrip("."))
    if os.path.exists(lp(dst)):
        print(f"farm link exists; same file as the staged copy: {os.path.samefile(lp(src), lp(dst))}")
    else:
        os.makedirs(lp(os.path.dirname(dst)), exist_ok=True)
        os.link(lp(src), lp(dst))
        print(f"linked {dst}")
    ok = sha256_file(dst) == DOTFILE_SHA
    print(f"sha256 matches the drive manifest: {ok}")
    return 0 if ok else 1


# ------------------------------------------------------------------------------------------ cli

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default=OUT_DEFAULT)
    ap.add_argument("--nas", default=NAS_DEFAULT)
    ap.add_argument("--repo", default=os.path.dirname(os.path.dirname(HERE)))
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("plan")
    sp.add_argument("--roots", default=ROOTS_DEFAULT)
    sp.add_argument("--from-b", default=os.path.join(ANALYSIS, "drives-dicom", "nonraw_for_A.csv"))
    sp.add_argument("--nested", default=os.path.join(OUT_DEFAULT, "nested_members.csv"))
    sub.add_parser("dotfile-farm")
    sub.add_parser("nested")
    sub.add_parser("worksheet").add_argument("--manifest", default=None)
    for name in ("copy", "verify", "holding"):
        s = sub.add_parser(name)
        s.add_argument("--manifest", default=None)
        s.add_argument("--project", nargs="*")
        s.add_argument("--execute", action="store_true")
        s.add_argument("--scratch", default=r"D:\projects\gjesus3\scratch_drives-nonraw-placement")
        s.add_argument("--by", default=f"Data Office ({getpass.getuser()})")
        s.add_argument("--sample", type=float, default=0.02)
        s.add_argument("--seed", type=int, default=20261003)
    args = ap.parse_args(argv)
    if getattr(args, "manifest", None) is None:
        args.manifest = os.path.join(args.out, "placement_manifest.csv")
    os.makedirs(args.out, exist_ok=True)
    return {"plan": cmd_plan, "dotfile-farm": cmd_dotfile_farm, "nested": cmd_nested, "worksheet": cmd_worksheet, "copy": cmd_copy, "verify": cmd_verify, "holding": cmd_holding}[args.cmd](args) or 0


if __name__ == "__main__":
    sys.exit(main())
