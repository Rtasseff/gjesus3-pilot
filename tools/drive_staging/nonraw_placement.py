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
sys.path.insert(0, HERE)                   # drive_staging/ -> historical_paths
import historical_paths as H  # noqa: E402  (THE destination rule: tasks/drives_nonraw_placement_review.md §6)

STAGING = r"D:\projects\gjesus3\staging"
ANALYSIS = os.path.join(STAGING, "_analysis")
OUT_DEFAULT = os.path.join(ANALYSIS, "drives-nonraw-placement")
NAS_DEFAULT = r"J:\gjesus3-data"
SCRATCH_DEFAULT = r"D:\projects\gjesus3\scratch_drives-nonraw-placement"
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
    "dest_rel", "decision", "reason", "note", "root_key", "shortened", "why",
]

# Ryan, 2026-10-04: MRI that has no reconstructed image, or whose reconstruction cannot be converted
# to DICOM, is NOT registered; it is kept as other data, beside a plain README saying why
# (stream B hands it over in nonraw_for_A v3 as kind notregistered:<reason>)
NOTREG_WHY = {
    "no-recon": "no reconstructed image (e.g. spectroscopy); gjesus3 registers MRI only as "
                "reconstructed DICOM images",
    "conversion-failed": "could not be converted to DICOM; if someone converts it, it can be registered",
}
NOTREG_README = "README_not_registered.txt"


def notreg_text(whys):
    lines = ["Why these files are not registered in gjesus3", "=============================================", "",
             "The MRI data in this folder (and its sub-folders) is kept here as OTHER DATA,",
             "not as a registered acquisition in gjesus3's archive. The reason:", ""]
    lines += [f"  - {w}" for w in sorted(whys)]
    lines += ["", "The files are byte-for-byte copies from the historical operator drives.",
              "Their original location is in _INDEX.csv (column original_path; column why).",
              "Questions: the Data Office.", ""]
    return "\r\n".join(lines)


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
    if os.path.basename(win(rec["member"].split(NESTED_SEP)[-1] if rec["archive"] else rec["relpath"])).startswith("._"):
        return "exclude", "system-file (macOS AppleDouble ._ stub)", None
    if cls == "archive" and INSTALLER_ARCHIVE_RE.search(win(rec["relpath"])):
        return "exclude", "software (installer archive)", None
    if is_personal(flag):
        return "exclude", "personal-admin-heuristic", None
    if is_zero(flag, rec["size"]):
        return "exclude", "zero-byte", None
    if cls == "archive" and not rec["archive"] and (rec.get("from_b") is not None or not rec.get("imaging_root")):
        # an archive outside B's roots, or one B handed over whole: its members decide
        return "expanded", "archive: its members are decided one by one", None
    if rec.get("nmr"):  # a TopSpin experiment (B's nmr_list.csv): spectrometer data, not imaging
        return "holding", "NMR (TopSpin) experiment: holding folder (Ryan, 2026-10-02)", None
    if rec.get("from_b") is not None:  # stream B's own non-raw list (nonraw_for_A.csv), its project
        proj = rec["from_b"] or None
        kind = rec.get("from_b_kind") or ""
        if kind.startswith("notregistered:"):
            sub = kind.split(":", 1)[1]
            if not proj:
                return "holding", "B->A not registered, no project", None
            return _project_decision(proj, ctx, f"B->A not registered ({sub})")
        if cls == "archive":  # B lists a nested archive whole; its inner content comes in B's v2 list
            return "unclear", "B->A nested archive: waiting for B's v2 (its contents), not placed whole", proj
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
        return "holding", "czi-unreadable with bytes: holding folder (Ryan, 2026-10-02)", None
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


NMR_DEFAULT = os.path.join(ANALYSIS, "drives-dicom", "nmr_list.csv")


def folder_view(archive, member):
    """A member path as stream B writes it (nmr_list.csv): a nested archive is a FOLDER named by its
    stem, and the nested archive's own repeated top folder is not repeated. Normalised segments."""
    chunks = member.replace("\\", "/").split(NESTED_SEP)
    out = []
    for i, chunk in enumerate(chunks):
        segs = [s for s in chunk.split("/") if s]
        if i < len(chunks) - 1:            # this chunk ends in a nested archive: use its stem
            segs[-1] = os.path.splitext(segs[-1])[0]
        elif i > 0 and segs and out and H.norm(segs[0]) == out[-1]:
            segs = segs[1:]                # the nested archive's repeated top folder
        out += [H.norm(s) for s in segs]
    return tuple(out)


def load_nmr(path):
    """B's TopSpin experiments: {(drive, archive or '-'): set of normalised experiment folders}."""
    out = collections.defaultdict(set)
    if not os.path.exists(path):
        return out
    for r in it(path):
        segs = tuple(H.norm(s) for s in re.split(r"[\\/]", r["path"]) if s)
        out[(r["drive"], r["archive"] or "-")].add(segs)
    return out


def is_nmr(nmr, drive, archive, path):
    """True if `path` (loose relpath, or a member path) lies in one of B's TopSpin experiments."""
    exps = nmr.get((drive, archive or "-"))
    if not exps:
        return False
    segs = folder_view(archive, path) if archive else tuple(H.norm(s) for s in path.split("\\") if s)
    return any(segs[:k] in exps for k in range(1, len(segs)))


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


def member_key(member):
    """Join key between the catalog's and the claims pass's member paths. The claims pass wrote .7z
    members with backslashes and lost accented characters to U+FFFD (78 Haizpea names), so compare
    with forward slashes and every non-ASCII character as `?`."""
    return re.sub(r"[^\x00-\x7f]", "?", member.replace("\\", "/"))


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
    nmr = load_nmr(args.nmr)
    say(f"NMR experiments (B's nmr_list): {sum(len(v) for v in nmr.values())} from {args.nmr}")
    say(f"imaging roots: {sum(len(v) for v in roots.values())} from {args.roots}")
    mapping = load_mapping(args.mapping) if args.mapping else {}
    mapping_used = collections.Counter()
    if args.mapping:
        say(f"2b mapping: {len(mapping)} groups mapped in {args.mapping}")
    fromb_kind = {}
    fromb = {}  # stream B's non-raw list: (drive, archive or '-', path) -> project ('' = none)
    if os.path.exists(args.from_b):
        for r in it(args.from_b):
            fromb[(r["drive"], r["archive"] or "-", r["path"])] = r["project"]
            fromb_kind[(r["drive"], r["archive"] or "-", r["path"])] = r.get("kind", "")
    say(f"B->A non-raw rows: {len(fromb)} from {args.from_b}")
    nested_rows = rd(args.nested) if os.path.exists(args.nested) else []
    nested_archives = {(r["drive"], r["archive"], r["nested"]) for r in nested_rows}
    nested_dedup = {}  # nested czi-raw already in production (scratchpad dedup -> nested_czi_dedup.csv)
    if os.path.exists(args.nested_dedup):
        for r in it(args.nested_dedup):
            nested_dedup[(r["drive"], r["nested"], r["inner"])] = f"{r['dedup']} {r['detail']}".strip()
    say(f"nested-archive members: {len(nested_rows)} in {len(nested_archives)} nested archives")

    rows = []

    def add(base, rec):
        dec, reason, proj = decide(rec, {"projects": projects})
        if dec == "holding" and mapping and mappable(reason):  # 2b: Ryan's group -> project
            d, who, series, _kind = manifest_group(base)
            nk = norm_key(key_string(d, who, series))
            if nk in mapping:
                mapping_used[nk] += 1
                dec, reason, proj = _project_decision(mapping[nk], {"projects": projects},
                                                      f"2b mapping ({who} | {series})")
        r = dict(base)
        r.update(decision=dec, reason=reason)
        kind = rec.get("from_b_kind") or ""
        if kind.startswith("notregistered:"):
            r["why"] = NOTREG_WHY.get(kind.split(":", 1)[1], kind)
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
    archive_fromb = {}  # an archive B handed over whole: its members take B's project
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
                   nmr=is_nmr(nmr, drive, "", f["relpath"]),
                   excluded_reason=excluded.get(f["relpath"]),
                   ingested=f["relpath"] in ingested_loose,
                   derived=derived.get((drive, f["relpath"])),
                   from_b=fromb.get((drive, "-", f["relpath"])),
                   from_b_kind=fromb_kind.get((drive, "-", f["relpath"])))
        add(base, rec)
        if f["class"] == "archive":
            archives[(drive, f["relpath"])] = rows[-1]
            archive_fromb[(drive, f["relpath"])] = rec["from_b"]
    say(f"loose files: {len(rows)}")

    # archive members: claims per member where the claims pass produced them, else the archive's own
    mclaims = {}
    for r in it(os.path.join(ANALYSIS, "codes", "archive_member_claims.csv")):
        # the claims pass wrote .7z member paths with backslashes; the catalog uses forward slashes
        mclaims[(CLAIMS_DRIVE[r["drive"]], r["archive_relpath"], member_key(r["member"]))] = r
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
    hit = sum(1 for m in members if (m["drive"], m["archive_relpath"], member_key(m["member"])) in mclaims)
    say(f"member claims matched to a catalog member: {hit} of {len(mclaims)} (LEONE has none)")
    for m in members:
        drive = m["drive"]
        arch = archives.get((drive, m["archive_relpath"]))
        if arch is None:
            say(f"!! member of an archive not in files.csv: {drive} {m['archive_relpath']}")
            continue
        mc = mclaims.get((drive, m["archive_relpath"], member_key(m["member"])))
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
                   nmr=is_nmr(nmr, drive, m["archive_relpath"], m["member"]),
                   excluded_reason=None,
                   ingested=(m["archive_relpath"], m["member"]) in ingested_member,
                   derived=None,
                   from_b=fromb.get((drive, m["archive_relpath"], m["member"]),
                                    archive_fromb.get((drive, m["archive_relpath"]))),
                   from_b_kind=fromb_kind.get((drive, m["archive_relpath"], m["member"])))
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
                   nmr=is_nmr(nmr, drive, n["archive"], n["nested"] + NESTED_SEP + n["inner"]),
                   excluded_reason=None, ingested=False, derived=None, from_b=None)
        rec["special"] = nested_special(n, nested_dedup.get((drive, n["nested"], n["inner"])))
        add(base, rec)

    # Simu_2_V_XYZ.zip and other unreadable archives: nothing listed -> the archive itself is unclear
    for a in rd(os.path.join(ANALYSIS, "catalog", "archives.csv")):
        if a["status"] not in ("ok",) and not INSTALLER_ARCHIVE_RE.search(win(a["archive_relpath"])):
            for r in rows:
                if not r["archive"] and r["relpath"] == a["archive_relpath"] and r["decision"] == "expanded":
                    r["decision"], r["reason"] = "exclude", (
                        f"not copied: truncated archive ({a['status']}), {gb(int(a['size']))} GB, remains on the "
                        f"owner's drive (Ryan, 2026-10-02); listed in the holding README and manifest")

    for i, r in enumerate(rows, 1):
        r["row"] = i
    if mapping:
        unused = [k for k in mapping if not mapping_used[k]]
        say(f"2b mapping: {sum(mapping_used.values())} non-raw files re-decided from {len(mapping) - len(unused)} "
            f"groups; {len(unused)} mapped groups matched no holding file (raw-only groups, or a stale key):")
        for k in unused:
            say(f"    unmatched: {k} -> {mapping[k]}")
    annotate_duplicates(rows, say)
    base_plan = not args.mapping and os.path.normcase(os.path.abspath(out)) == os.path.normcase(OUT_DEFAULT)
    assign_destinations(rows, projects, args.nas, out, say, load_claim_roots(),
                        global_index=os.path.join(args.repo, "tasks", "drives_nonraw_index.csv") if base_plan else None)
    check_nas(rows, args.nas, projects, say)
    wcsv(os.path.join(out, "placement_manifest.csv"), MANIFEST_FIELDS, rows)
    write_summaries(rows, out, args.repo if base_plan else None, say, leone)
    with io.open(os.path.join(out, "plan.log"), "a", encoding="utf-8") as f:
        f.write("\n".join(log) + "\n\n")


NESTED_PERSONAL_RE = re.compile(r"Meals cost original documents\.zip$", re.I)  # meal receipts (B, 2026-10-02)


def nested_special(n, dedup=None):
    """Per-file decisions for nested-archive members that the general rules would get wrong.
    `dedup`: this czi's verdict from nested_czi_dedup.csv (`in-production-...` = already ingested)."""
    if NESTED_PERSONAL_RE.search(n["nested"]):
        return ("exclude", "personal-admin (meal receipts archive)", None)
    if n["class"] == "czi-raw" and dedup and dedup.startswith("in-production"):
        return ("exclude", f"czi-raw (nested; {dedup.split()[0]}: see nested_czi_dedup.csv)", None)
    if n["class"] == "czi-raw":
        return ("raw-oneoff", "czi-raw inside a nested archive: never seen by the .czi ingest -> /raw/ "
                              "one-off (dedup against production first)", None)
    if n["ext"].lower() == ".svs":
        return ("holding", "Aperio .svs whole-slide scan (instrument not onboarded): holding folder "
                           "(Ryan, 2026-10-02)", None)
    return None


# ------------------------------------------------------------------- destinations (historical_paths)

HOLDING_BASE = "staging\\historical_drives_unassigned"


def tree_base(r, projects):
    """The tree a row lands in: a project's working\\historical_drives, or the holding folder."""
    if r["decision"] == "holding":
        return HOLDING_BASE
    return "\\".join(["projects", project_folder(r["project_name"], projects), *SUBDIR])


def load_claim_roots():
    """claims.csv -> {normalised claim-root segments: project name}, for every claim that names a
    project (CONFIRMED, A, B incl. the 0720 fold, and SHADOWED claims with a proposed project --
    those are often the OUTER folders)."""
    out = {}
    for c in it(os.path.join(ANALYSIS, "codes", "claims.csv")):
        proj = project_for(c["verdict"], c["proposed_project"], c["claim_root"])
        if not proj and c["verdict"] == "SHADOWED":
            proj = c["proposed_project"] or None
        if proj:
            key = H.claim_root_segments(c["claim_root"])
            out[key] = proj
            if c["source"] in ("filename", "archive-member-filename"):
                FILENAME_ROOTS.add(key)   # the root is just the folder of a file whose NAME held the code
    return out


FILENAME_ROOTS = set()

# Ryan, 2026-10-04 ("group under the parent"): in these projects a study folder that is only a
# session / animal level folder is replaced by its parent, so the sessions sit together as on the drive
PARENT_GROUP_PROJECTS = {"AE-biomaGUNE-0721", "AE-biomaGUNE-1019", "AE-biomaGUNE-1123", "AE-biomaGUNE-1321"}
SESSION_OR_ANIMAL_RE = re.compile(
    r"^\d{8}_\d{6}_"                 # a ParaVision session  20221006_120152_jrc221006_m42_0721_1_1
    r"|^id\s?\d+[a-z]?$"             # an animal             ID205, ID 22
    r"|(^|_)m\d+[a-z]?(_|$)"         # an animal             m36, Splits_m5_1019_End-Expiration
    r"|^grupo\s+[a-z]$",             # an animal group       Grupo B
    re.I)


def promote_root(names, kinds, i, from_filename, code=""):
    """Ryan's "group under the parent": climb from root index i while the folder is session / animal
    level (or, on the first step, only the folder of a file-name claim -- unless that folder's own
    name carries the project code: then it IS the study folder, e.g. `Proyecto 1019 ...`). Never onto
    the drive's top folder, never past an archive."""
    first = True
    while i > 1 and kinds[i - 1] == "dir" and kinds[i] == "dir":
        named_for_project = bool(code) and code in names[i]
        if not (SESSION_OR_ANIMAL_RE.search(names[i]) or (first and from_filename and not named_for_project)):
            break
        i -= 1
        first = False
    return i


def row_root(r, claim_roots):
    """The root folder (normalised segment tuple) for a row, or None (keep the full path):
      - a 2b-mapped row: the folder of its worksheet group (its `series`);
      - a row placed in a project: the OUTERMOST claim root of THAT project on its path;
      - holding: None."""
    if r["decision"] == "holding" or not r.get("project_name"):
        return None
    if r.get("root_key") and not r["reason"].startswith("2b mapping") and r["project_name"] not in RECOMPUTE_ROOTS:
        return None if r["root_key"] == "-" else tuple(r["root_key"].split("|"))  # computed earlier
    segs = H.logical_segments(r["relpath"], r["archive"], r["member"])
    names = [H.norm(n) for n, _k in segs]
    kinds = [k for _n, k in segs]
    if r["reason"].startswith("2b mapping"):
        _d, _who, series, _kind = manifest_group(r)
        if series.startswith("("):
            return None
        toks = [H.norm(t) for t in re.split(r"[\\/!]", series) if t]
        pos = -1
        for t in toks:                         # the group's folders, in order (gaps allowed)
            try:
                pos = names.index(t, pos + 1, len(names) - 1)
            except ValueError:
                return None
        return tuple(names[: pos + 1])
    for i in range(len(names) - 1):            # outermost first
        if claim_roots.get(tuple(names[: i + 1])) == r["project_name"]:
            if r["project_name"] in PARENT_GROUP_PROJECTS:
                i = promote_root(names, kinds, i, tuple(names[: i + 1]) in FILENAME_ROOTS,
                                 code=r["project_name"][-4:])
            return tuple(names[: i + 1])
    return None


RECOMPUTE_ROOTS = set()  # projects whose stored root_key is ignored (paths --recompute-roots)


def plan_tree(base, rows, claim_roots, nas, budget):
    """Plan one tree with historical_paths. -> (planner, items, {row id: dest})."""
    p = H.Planner(base, budget=budget)
    p.load_pathmap(os.path.join(nas, base, H.PATHMAP_NAME))
    items = []
    for r in rows:
        root = row_root(r, claim_roots)
        r["root_key"] = "|".join(root) if root else "-"
        items.append(H.Item(id=str(r["row"]), drive=r["drive"], relpath=r["relpath"], archive=r["archive"],
                            member=r["member"], root=root,
                            extra={"size": r["size"], "sha256": r["sha256"], "claim_id": r["claim_id"],
                                   "why": r.get("why", "")}))
    return p, items, p.plan(items)


def assign_destinations(rows, projects, nas, out, say, claim_roots, global_index=None):
    """Replace every placed / closed-project / holding row's dest_rel by the historical_paths rule,
    tree by tree, and write the index / pathmap / README / origin PREVIEWS under <out>\\trees\\.
    Reports, per rule, the max length and the count over the budget (on \\\\GJESUS3\\gjesus3\\)."""
    trees = collections.defaultdict(list)
    for r in rows:
        if r["decision"] in ("place", "closed-project", "holding"):
            trees[tree_base(r, projects)].append(r)
    def legacy(r):  # the first layout (full path, <stem>_<ext> archive folders), for the R0 line only
        if r["decision"] == "holding":
            return holding_rel(r["drive_label"], r["relpath"], r["archive"], r["member"])
        return dest_rel(project_folder(r["project_name"], projects), r["drive_label"], r["relpath"],
                        r["archive"], r["member"])
    stat = {"R0 old layout (full path, archive folders)": [legacy(r) for rs in trees.values() for r in rs]}
    flat = []
    for base, rs in sorted(trees.items()):
        _p, _items, d = plan_tree(base, rs, claim_roots, nas, budget=10 ** 9)
        flat += list(d.values())
    stat["R1 root first, high-level folders dropped"] = flat
    final, failed = [], []
    gidx = []
    for base, rs in sorted(trees.items()):
        try:
            p, items, d = plan_tree(base, rs, claim_roots, nas, budget=H.BUDGET)
        except H.BudgetError as e:  # reported, then the run STOPS before any manifest is written
            failed.append(f"{base}: {e}")
            continue
        byid = {str(r["row"]): r for r in rs}
        for it_ in items:
            byid[it_.id]["dest_rel"] = d[it_.id]
            byid[it_.id]["shortened"] = "Y" if it_.extra.get("shortened") else "N"
            final.append(d[it_.id])
        tdir = os.path.join(out, "trees", base.replace("\\", "__"))
        idx = H.index_rows(d, items, base)
        H.write_index(os.path.join(tdir, H.INDEX_NAME), idx)
        H.write_pathmap(os.path.join(tdir, H.PATHMAP_NAME), p.pathmap_rows())
        notreg = notreg_folders(base, [(d[i.id], byid[i.id].get("why", "")) for i in items if byid[i.id].get("why")])
        wcsv(os.path.join(tdir, "_NOTREG.csv"), ["folder", "why"],
             [{"folder": f, "why": w} for f, ws in sorted(notreg.items()) for w in sorted(ws)])
        origins = p.origins(items)
        wcsv(os.path.join(tdir, "_ORIGINS.csv"), ["folder", "original"],
             [{"folder": k, "original": o} for k, v in sorted(origins.items()) for o in v])
        with io.open(os.path.join(tdir, "_ORIGIN_preview.txt"), "w", encoding="utf-8", newline="\r\n") as f:
            for folder, origs in sorted(origins.items()):
                f.write(f"== {folder}\\{H.ORIGIN_NAME}\n" + H.origin_text(origs).replace("\r\n", "\n") + "\n")
        gidx += [dict(x, tree=base) for x in idx]
    stat["R2 + fewest folders shortened (final)"] = final
    say("\nPATH LENGTH, per rule (UNC \\\\GJESUS3\\gjesus3\\..., budget %d)" % H.BUDGET)
    for name, dests in stat.items():
        lens = [H.unc_len(x) for x in dests if x]
        say(f"  {name:48s} files {len(lens):6d}  max {max(lens) if lens else 0:4d}  "
            f"> {H.BUDGET}: {sum(1 for x in lens if x > H.BUDGET):5d}  > 259: {sum(1 for x in lens if x > 259):5d}")
    short = sum(1 for x in gidx if x["shortened"] == "Y")
    say(f"  shortened (a folder or the file name on the way): {short} files")
    for f_ in failed:
        say(f"  !! {f_}")
    if failed:  # never write a manifest whose destinations break the budget, nor touch decisions
        raise SystemExit(f"STOPPED: {len(failed)} tree(s) cannot meet the {H.BUDGET}-character budget; "
                         f"nothing written (see above)")
    if global_index:
        # the committed Data Office index: PROJECT trees only, slim columns (the per-tree _INDEX.csv on
        # the NAS and the D: manifest carry sha256 etc.; the holding folder has its own manifest.csv)
        gcols = ["project", "new_path", "original_path", "size", "claim_id", "shortened"]
        prow = [dict(g, project=g["tree"].split("\\")[1]) for g in gidx if g["tree"].startswith("projects\\")]
        # new_path is relative to <project>\working\historical_drives\
        wcsv(global_index, gcols, prow)
        say(f"  global index (project trees): {len(prow)} rows -> {global_index}")


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
    if repo:  # the committed record: only the base plan (default --out, no --mapping) writes it
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
                    nz = self._zips[key] = zipfile.ZipFile(lp(extract_nested(ap, nested, self.scratch)))
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
    if r.get("_src"):  # copy --from-holding: the file's copy in the NAS holding folder (bytes re-verified)
        src = open(lp(r["_src"]), "rb")
    else:
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


_VERSION = []


def provenance_version():
    """`nonraw_placement.py (gjesus3-pilot tools) @ <sha>` -- computed once (it runs git)."""
    if not _VERSION:
        from ingest import provenance
        _VERSION.append(provenance.software_version_string("nonraw_placement.py"))
    return _VERSION[0]


def prov_entry(r, run_id, by, today):
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
            "software_version": provenance_version(),
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
    projects = load_projects(args.nas)
    # a `closed-project` row is placeable once the LIVE registry says its project is active again
    # (Ryan reopens case by case: 1519 / 0320 on 2026-10-04)
    reopened = {n for n, p in projects.items() if (p.get("status") or "").strip().lower() == "active"}
    rows = [r for r in load_manifest(args.manifest)
            if r["decision"] == "place" or (r["decision"] == "closed-project" and r["project_name"] in reopened)]
    if args.project:
        rows = [r for r in rows if r["project_name"] in args.project]
    held = sorted({r["project_name"] for r in load_manifest(args.manifest)
                   if r["decision"] == "closed-project" and r["project_name"] not in reopened})
    if held:
        print(f"still closed, not copied: {held}")
    if args.from_holding:
        # 2b after the D: staging is gone: a mapped group's files are read from their copy in the NAS
        # holding folder (filled by `holding --execute`). Rows placed earlier from D: are already at
        # their destination and are skipped as identical before any source is opened.
        absent = 0
        for r in rows:
            if r["reason"].startswith("2b mapping"):
                r["_src"] = os.path.join(args.nas, holding_rel(r["drive_label"], r["relpath"], r["archive"], r["member"]))
                absent += not os.path.exists(lp(r["_src"]))
        print(f"--from-holding: {sum(1 for r in rows if r.get('_src'))} mapped files read from the holding folder; "
              f"{absent} of them are NOT there")
        if absent and args.execute:
            return 2
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
        lens = [H.unc_len(r["dest_rel"]) for r in rows]
        exists = ndocs = 0
        for p, rs in by_proj.items():
            base = "\\".join(["projects", project_folder(p, projects), *SUBDIR])
            if os.path.isdir(lp(os.path.join(args.nas, base))):
                exists += sum(1 for r in rs if os.path.exists(lp(os.path.join(args.nas, r["dest_rel"]))))
            nd = len(publish_tree(args.nas, args.manifest, base, execute=False))
            ndocs += nd
            print(f"  {p:28s} {len(rs):6d} files {gb(sum(int(r['size']) for r in rs)):>8s} GB"
                  f"  + {nd:3d} index documents  -> {base}")
        print(f"destinations already present: {exists}; longest UNC path {max(lens) if lens else 0} "
              f"(budget {H.BUDGET}); over budget: {sum(1 for x in lens if x > H.BUDGET)}; "
              f"index documents to write: {ndocs}")
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
            if stats["COLLISION"]:
                print(f"  {proj}: collisions -- index documents NOT published", flush=True)
                continue
            base = "\\".join(["projects", project_folder(proj, projects), *SUBDIR])
            docs = publish_tree(args.nas, args.manifest, base, execute=True)
            proj_root = "\\".join(base.split("\\")[:2]) + "\\"
            append_provenance(prov_path, [{
                "output_path": rel[len(proj_root):].replace("\\", "/"),
                "output_name": rel.split("\\")[-1], "file_type": os.path.splitext(rel)[1],
                "date_created": today, "creator": by, "input_refs": "",
                "process_description": "Index / README / origin note for the historical-drive material in "
                                       "working/historical_drives (nonraw_placement.py; rule: historical_paths.py)",
                "software_version": provenance_version(), "parameters_ref": run_id, "lab_notebook_ref": "",
                "notes": "tool-owned document; rewritten when more material is added"} for rel, _w in docs])
            print(f"  {proj}: {len(docs)} index documents published "
                  f"({sum(1 for _r, w in docs if w)} written, the rest unchanged)", flush=True)
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
    """Count/bytes per project from the NAS + a random re-hash sample (place rows, and closed-project
    rows of projects since reopened)."""
    rows = [r for r in load_manifest(args.manifest) if r["decision"] in ("place", "closed-project")]
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
    FRIO-X6       (drive1_FRIO-X6, serial 2322E4A111E7)
    MFB-Disco-2   (drive2_MFB-Disco-2, serial 2322E4A112BD)
  The folders below keep the drives' own directory structure, so a folder name may
  tell you which study or person a file came from. A .zip or .7z archive became a
  normal folder named like Manon_zip.

Why it is here and not in gjesus3
  These files are NOT part of the gjesus3 archive. They are not raw data (the raw
  acquisitions from these drives were ingested into gjesus3 separately), and they
  have not been assigned to a project.

  Left out on purpose: installed software, system files, and personal or
  administrative documents.

Some folder names were shortened
  Windows cannot open very long paths, so a few long folder or file names were
  cut to 24 (sometimes 12) characters plus a short code, for example
  Comparasion expiration v~3f2a. Nothing was lost: every file is a byte-for-byte
  copy, and manifest.csv gives each file's full original path.

Not copied
  Simu_2_V_XYZ.zip (drive FRIO-X6, 97 GB): the archive is truncated and cannot be
  opened, so it was not copied. It remains on the owner's drive.

The originals
  The originals remain on the owners' external drives.

If you need something placed in a project
  Ask the Data Office. Tell us the file or folder and the project it belongs to.

manifest.csv lists every file here: its path here (new_path), where it was on
the drive (original_path), size and SHA-256 (taken from the drive manifests when
the drives were staged). Open it in Excel and use Search (Ctrl+F) or a filter.
_PATHMAP.csv is for the Data Office; please do not edit it.
"""


def write_if_changed(path, data):
    """Tool-owned documents only (index, README, pathmap, origin) -- never a data file. Writes via a
    temp file + replace, and only when the bytes differ. -> True if written."""
    p = lp(path)
    if os.path.exists(p):
        with open(p, "rb") as f:
            if f.read() == data:
                return False
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".~nonraw.tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, p)
    return True


def tree_preview_dir(manifest, base):
    return os.path.join(os.path.dirname(manifest), "trees", base.replace("\\", "__"))


def tree_documents(manifest, base, holding=False, extra_index_rows=()):
    """{path relative to the NAS root: bytes} for one tree, from `plan`'s previews (so what was
    reviewed is exactly what is published)."""
    tdir = tree_preview_dir(manifest, base)
    docs = {}
    rows = rd(os.path.join(tdir, H.INDEX_NAME)) + list(extra_index_rows)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=H.INDEX_FIELDS, extrasaction="ignore", lineterminator="\r\n")
    w.writeheader()
    w.writerows(rows)
    docs[f"{base}\\{'manifest.csv' if holding else H.INDEX_NAME}"] = buf.getvalue().encode("utf-8-sig")
    with open(os.path.join(tdir, H.PATHMAP_NAME), "rb") as f:
        docs[f"{base}\\{H.PATHMAP_NAME}"] = f.read()
    readme = README_TXT if holding else H.PROJECT_README
    docs[f"{base}\\{H.README_NAME}"] = readme.replace("\n", "\r\n").encode("utf-8")
    origins = collections.defaultdict(list)
    op = os.path.join(tdir, "_ORIGINS.csv")
    if os.path.exists(op):
        for r in rd(op):
            origins[r["folder"]].append(r["original"])
    for folder, origs in origins.items():
        docs[f"{base}\\{folder}\\{H.ORIGIN_NAME}"] = H.origin_text(origs).encode("utf-8")
    nrp = os.path.join(tdir, "_NOTREG.csv")
    if os.path.exists(nrp):
        nr = collections.defaultdict(set)
        for r in rd(nrp):
            nr[r["folder"]].add(r["why"])
        for folder, whys in nr.items():
            docs[f"{base}\\{folder}\\{NOTREG_README}"] = notreg_text(whys).encode("utf-8")
    return docs


def notreg_folders(base, dest_whys):
    """{folder below base: {why}} -- one README per GROUP: the topmost folder holding not-registered
    files (an exam folder), moved up while its README path would break the budget."""
    folders = collections.defaultdict(set)
    for dest, why in dest_whys:
        folders[os.path.dirname(dest)[len(base) + 1:]].add(why)
    keep = {}
    for f in sorted(folders, key=lambda x: (x.count("\\"), x.lower())):
        if any(f.lower().startswith(k.lower() + "\\") for k in keep):
            for k in keep:
                if f.lower().startswith(k.lower() + "\\"):
                    keep[k] |= folders[f]
            continue
        keep[f] = set(folders[f])
    out = collections.defaultdict(set)
    for f, whys in keep.items():
        while H.unc_len(f"{base}\\{f}\\{NOTREG_README}") > H.BUDGET and f.count("\\") > 0:
            f = os.path.dirname(f)
        out[f] |= whys
    return out


def publish_tree(nas, manifest, base, execute, holding=False, extra_index_rows=()):
    """Write a tree's documents to the NAS (or, dry run, list them). -> [(rel path, written?)]"""
    out = []
    for rel, data in sorted(tree_documents(manifest, base, holding, extra_index_rows).items()):
        full = os.path.join(nas, rel)
        if len("\\\\GJESUS3\\gjesus3\\" + rel) > H.BUDGET:
            raise SystemExit(f"document path over budget: {rel}")
        out.append((rel, write_if_changed(full, data) if execute else None))
    return out


def not_copied_rows(manifest_rows):
    """Index rows for material deliberately NOT copied but listed (Ryan, 2026-10-02): Simu_2_V_XYZ.zip."""
    out = []
    for r in manifest_rows:
        if r["decision"] == "exclude" and r["reason"].startswith("not copied:"):
            out.append({"new_path": "", "drive": r["drive_label"], "archive": "",
                        "original_path": H.original_display(r["drive"], r["relpath"]),
                        "size": r["size"], "sha256": r["sha256"], "claim_id": r["claim_id"],
                        "shortened": "N",
                        "note": "not copied: truncated archive, 97 GB, remains on the owner's drive"})
    return out


def cmd_holding(args):
    """2c: copy every `holding` row into staging\\historical_drives_unassigned\\ (same verified copy as
    the projects), then publish README.txt, manifest.csv (every file's new + original path, size,
    sha256, plus the not-copied archive) and _PATHMAP.csv. Dry run unless --execute."""
    allrows = load_manifest(args.manifest)
    rows = [r for r in allrows if r["decision"] == "holding"]
    root = os.path.join(args.nas, HOLDING_BASE)
    n = sum(int(r["size"]) for r in rows)
    print(f"{'EXECUTE' if args.execute else 'DRY RUN'}: {len(rows)} files, {gb(n)} GB -> {root}")
    by = collections.Counter((r["drive_label"], r["class"]) for r in rows)
    for k, c in sorted(by.items()):
        print(f"  {k[0]:20s} {k[1]:16s} {c:7d}")
    print(f"  by reason: {dict(collections.Counter(r['reason'].split(':')[0][:40] for r in rows))}")
    print(f"  of which archive members: {sum(1 for r in rows if r['archive'])}")
    lens = [H.unc_len(r["dest_rel"]) for r in rows]
    print(f"  longest UNC path {max(lens) if lens else 0} (budget {H.BUDGET}); over budget: "
          f"{sum(1 for x in lens if x > H.BUDGET)}")
    print(f"  existing holding folder: {os.path.isdir(lp(root))}")
    extra = not_copied_rows(allrows)
    docs = tree_documents(args.manifest, HOLDING_BASE, holding=True, extra_index_rows=extra)
    for rel, data in docs.items():  # previews of exactly what will be published
        name = rel[len(HOLDING_BASE) + 1:].replace("\\", "__")
        with open(os.path.join(args.out, "holding_preview__" + name), "wb") as f:
            f.write(data)
    print(f"  documents: {len(docs)} (README.txt, manifest.csv incl. {len(extra)} not-copied row, _PATHMAP.csv); "
          f"previews: {args.out}\\holding_preview__*")
    if not args.execute:
        return 0
    members = MemberSource(args.scratch)
    for ap, mems in sorted(_sevenzip_members(rows).items()):
        members.prepare_7z(ap, mems)
    stats = collections.Counter()
    for i, r in enumerate(rows, 1):
        try:
            stats[copy_one(r, args.nas, members)] += 1
        except Collision as e:
            stats["COLLISION"] += 1
            print(f"  COLLISION (untouched): {e}")
        if i % 1000 == 0:
            print(f"  {i}/{len(rows)} {dict(stats)}", flush=True)
    members.close()
    if not stats["COLLISION"]:
        written = publish_tree(args.nas, args.manifest, HOLDING_BASE, execute=True, holding=True,
                               extra_index_rows=extra)
        print(f"  documents published: {sum(1 for _r, w in written if w)} written")
    print(dict(stats))
    return 1 if stats["COLLISION"] else 0


# --------------------------------------------------------------------------------------- nested

NESTED_FIELDS = ["drive", "archive", "nested", "inner", "size", "sha256", "class", "ext", "flag",
                 "czi_instrument", "czi_rule", "czi_acq_datetime", "czi_stand", "err"]
NESTED_SKIP_OUTER = {LEONE, "Cardiac MRI.zip"}  # streams C and B list their own


def extract_nested(outer, member, scratch):
    """Copy a nested archive out of its outer zip into scratch ONCE, then read it from disk.
    zipfile on top of an outer member stream re-reads the outer from the start on every backward
    seek -- quadratic, and it stalled on a 2.3 GB nested zip (2026-10-02)."""
    tag = hashlib.sha1(f"{outer}!{member}".encode("utf-8")).hexdigest()[:10]
    dst = os.path.join(scratch, "nested", f"{tag}_{os.path.basename(member)}")
    with zipfile.ZipFile(lp(outer)) as oz:
        size = oz.getinfo(member).file_size
        if os.path.exists(lp(dst)) and os.path.getsize(lp(dst)) == size:
            return dst
        os.makedirs(lp(os.path.dirname(dst)), exist_ok=True)
        with oz.open(member) as src, open(lp(dst + ".part"), "wb") as out:
            shutil.copyfileobj(src, out, 8 << 20)  # zipfile checks the member's CRC at EOF
    os.replace(lp(dst + ".part"), lp(dst))
    return dst


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
        local = extract_nested(outer, m["member"], args.scratch)
        with zipfile.ZipFile(lp(local)) as iz:
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


# `project` + `note_for_ryan` first (what Ryan types); `group_key` last (the machine join key --
# never edit it). G-numbers are display order only.
WORKSHEET_FIELDS = ["group", "priority", "project", "note_for_ryan", "drive", "researcher", "series", "kind",
                    "nonraw_files", "nonraw_gb", "raw_acqs_blank_project", "date_min", "date_max",
                    "example_1", "example_2", "example_3", "acq_ids", "group_key"]


MAPPABLE_REASONS = ("no claim", "(C) claim", "B->A non-raw, no project", "B->A not registered, no project")


def mappable(reason):
    """A holding row Ryan may map in 2b. NOT the ones whose holding is a decision of its own (Ryan,
    2026-10-02): .lsm, Aperio .svs, TopSpin NMR, unreadable .czi."""
    return reason in MAPPABLE_REASONS


def group_key(drive, researcher, relpath, verdict, claim_id, member=""):
    """THE 2b group of a file or a blank-project acquisition -> (drive, researcher, series, kind).

    One definition, used by `worksheet` (to build the rows Ryan maps) and by `plan --mapping` /
    `apply-raw` (to apply them), so a mapped group is exactly the set of files it was shown with.
    `member` is the archive member path (outer member for nested archives) or "" for a loose file.
      (C) claim                  -> one group per claim id
      member of a DRIVE-ROOT archive -> the archive + "!" + the member's first two folders below
                                    the archive's own repeated top folder (these archives are
                                    whole libraries: Drive zuri, Maria Jesus/Irati, Haizpea)
      anything else (a loose file, or a member of an archive inside a researcher's folder)
                                 -> project_claims.py's (researcher, series) rule on the path, so
                                    an archive groups with the loose files around it"""
    if verdict == "C":
        return drive, researcher, f"(C) {claim_id}", "(C) claim"
    if member and "\\" not in relpath:
        stem = os.path.splitext(relpath)[0]
        folders = member.replace("\\", "/").split("/")[:-1]
        if folders and folders[0] == stem:
            folders = folders[1:]
        return drive, researcher, relpath + "!" + ("/".join(folders[:2]) or "(top level)"), "no claim"
    return drive, researcher, series_of(relpath, researcher), "no claim"


def key_string(drive, researcher, series):
    """The stable join key written into the worksheet (`group_key` column). G-numbers are only a
    display order and change when the worksheet is regenerated; never join on them."""
    return f"{drive}|{researcher}|{series}"


def manifest_group(r):
    return group_key(r["drive"], r["researcher"], r["relpath"], r["verdict"], r["claim_id"],
                     r["member"].split(NESTED_SEP)[0] if r["archive"] else "")


def blank_list_group(a):
    verdict = a["verdict"] if a["verdict"] == "C" else ""
    return group_key(a["drive"], a["researcher"], a["archive"] or a["relpath"], verdict, a["claim_id"],
                     a["member"] if a["archive"] else "")


def norm_key(key):
    """Accent- and case-blind form of a group key: Excel may re-save the worksheet in ANSI and lose
    the `ñ` of `Zuriñe`, so the join compares with every non-ASCII character as `?`."""
    return re.sub(r"[^\x00-\x7f]", "?", key or "").strip().lower()


def read_worksheet(path):
    """Read the worksheet as Ryan saved it. Tolerates what Excel does to a CSV on a Spanish-locale
    machine: `;` instead of `,`, ANSI (cp1252) instead of UTF-8, a BOM or not."""
    raw = open(path, "rb").read()
    for enc in ("utf-8-sig", "cp1252"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    first = text.splitlines()[0] if text else ""
    delim = ";" if first.count(";") > first.count(",") else ","
    return list(csv.DictReader(io.StringIO(text), delimiter=delim))


def load_mapping(path):
    """A filled-in worksheet -> {norm_key(group_key): project name} (rows with `project` filled)."""
    out = {}
    for r in read_worksheet(path):
        p = (r.get("project") or "").strip()
        if p:
            if not r.get("group_key"):
                raise SystemExit(f"worksheet row {r.get('group')} has a project but no group_key: "
                                 f"the column was deleted or edited -- restore it from git")
            out[norm_key(r["group_key"])] = p
    return out


def cmd_worksheet(args):
    """2b: one row per no-claim group (noclaim_groups.csv) plus one per (C)-claim group, with the
    holding-bound non-raw files and the blank-project raw acquisitions it would map. Refuses to
    overwrite a worksheet in which any `project` cell is already filled (that is Ryan's work)."""
    path = os.path.join(args.repo, "tasks", "drives_nonraw_mapping_worksheet.csv")
    if os.path.exists(path) and load_mapping(path) and not args.force:
        print(f"REFUSED: {path} already has {len(load_mapping(path))} mapped groups (Ryan's answers). "
              f"Copy it aside first, or pass --force if you really mean to discard them.")
        return 2
    rows = load_manifest(args.manifest)
    groups = {}
    for g in it(os.path.join(ANALYSIS, "codes", "noclaim_groups.csv")):
        d = CLAIMS_DRIVE[g["drive"]]
        groups[(d, g["researcher"], g["series"])] = {
            "drive": d, "researcher": g["researcher"], "series": g["series"], "kind": "no claim",
            "files": [], "bytes": 0, "acqs": [], "dates": [g["date_min"], g["date_max"]]}

    def grp(gk):
        drive, researcher, series, kind = gk
        key = (drive, researcher, series)
        if key not in groups:
            groups[key] = {"drive": drive, "researcher": researcher, "series": series, "kind": kind,
                           "files": [], "bytes": 0, "acqs": [], "dates": []}
        return groups[key]

    for r in rows:
        if r["decision"] != "holding" or not mappable(r["reason"]):  # decided holding: not mapped
            continue
        g = grp(manifest_group(r))
        g["files"].append(r["member"] or r["relpath"])
        g["bytes"] += int(r["size"])
    for a in it(os.path.join(args.repo, "tasks", "drives_blank_project_list.csv")):
        g = grp(blank_list_group(a))
        g["acqs"].append(a["acq_id"])
        g["dates"].append(a["acquisition_date"])
    out = []
    for (d, who, series), g in groups.items():
        if not g["files"] and not g["acqs"]:
            continue
        ex = sorted(set(os.path.basename(f.replace("/", "\\")) for f in g["files"]))[:3]
        dates = sorted(x for x in g["dates"] if x)
        out.append({"group_key": key_string(d, who, series),
                    "drive": DRIVES[d][0], "researcher": who, "series": series, "kind": g["kind"],
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
        # A = worth Ryan's time (>= 1 GB of non-raw, or >= 20 blank-project acquisitions); B = the long
        # tail, which may simply stay blank (-> holding folder)
        x["priority"] = "A" if x["_bytes"] >= 1e9 or x["raw_acqs_blank_project"] >= 20 else "B"
    # UTF-8 WITH a BOM: Excel then opens the accents correctly (a researcher folder is `Zuriñe`).
    with io.open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=WORKSHEET_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(out)
    print(f"worksheet: {len(out)} groups -> {path}")
    print(f"  non-raw files {sum(x['nonraw_files'] for x in out)}, "
          f"{gb(sum(x['_bytes'] for x in out))} GB; blank raw acqs {sum(x['raw_acqs_blank_project'] for x in out)}")
    return 0


def remap_rows(rows, mapping, projects):
    """The pure part of `remap`: holding rows of a mapped group -> place / closed-project / unclear,
    with the project's dest_rel. Same decision as `plan --mapping`, from a stored manifest."""
    out, used = [], collections.Counter()
    for r in rows:
        r = dict(r)
        if r["decision"] == "holding" and mappable(r["reason"]):
            d, who, series, _kind = manifest_group(r)
            nk = norm_key(key_string(d, who, series))
            if nk in mapping:
                used[nk] += 1
                dec, reason, proj = _project_decision(mapping[nk], {"projects": projects},
                                                      f"2b mapping ({who} | {series})")
                prow = projects.get(proj)
                r.update(decision=dec, reason=reason, project_name=proj,
                         project_id=prow["project_id"] if prow else "NEW",
                         project_status=prow["status"] if prow else "not-in-registry")
                r["dest_rel"] = (dest_rel(project_folder(proj, projects), r["drive_label"], r["relpath"],
                                          r["archive"], r["member"]) if dec in ("place", "closed-project") else "")
        out.append(r)
    return out, used


def safe_claim_roots():
    """claims.csv roots if D: still has them; {} otherwise (stored root_keys then carry the rule)."""
    try:
        return load_claim_roots()
    except FileNotFoundError:
        return {}


def cmd_paths(args):
    """Re-plan the destinations of an existing manifest with the historical_paths rule (no catalog
    read; seconds instead of minutes). Same decisions; new dest_rel / root_key; previews under
    <out>\\trees\\. On the record manifest it also rewrites the committed global index."""
    rows = load_manifest(args.manifest)
    projects = load_projects(args.nas)
    RECOMPUTE_ROOTS.update(args.recompute_roots or [])
    log = []

    def say(m):
        print(m, flush=True)
        log.append(m)
    is_record = os.path.normcase(os.path.abspath(args.out)) == os.path.normcase(OUT_DEFAULT)
    assign_destinations(rows, projects, args.nas, args.out, say, safe_claim_roots(),
                        global_index=os.path.join(args.repo, "tasks", "drives_nonraw_index.csv") if is_record else None)
    wcsv(os.path.join(args.out, "placement_manifest.csv"), MANIFEST_FIELDS, rows)
    write_summaries(rows, args.out, args.repo if is_record else None, say, 0)
    with io.open(os.path.join(args.out, "plan.log"), "a", encoding="utf-8") as f:
        f.write(f"paths {dt.datetime.now():%Y-%m-%d %H:%M}\n" + "\n".join(log) + "\n\n")
    return 0


def cmd_remap(args):
    """2b WITHOUT the catalog: apply Ryan's worksheet to a stored manifest (stream A's record
    `placement_manifest.csv`, or its copy kept off D: before the staging is erased). Writes
    <out>\\placement_manifest.csv for `copy` (use `copy --from-holding` once D: is gone)."""
    if os.path.normcase(os.path.abspath(args.out)) == os.path.normcase(OUT_DEFAULT):
        print("REFUSED: give a NEW --out folder; the default one holds stream A's record manifest")
        return 2
    mapping = load_mapping(args.mapping)
    projects = load_projects(args.nas)
    rows, used = remap_rows(load_manifest(args.manifest), mapping, projects)
    # destinations by the shared rule; rows placed earlier keep theirs (their root_key is stored and
    # the NAS _PATHMAP.csv freezes their folders), so no claims.csv / D: is needed here
    assign_destinations(rows, projects, args.nas, args.out, print, safe_claim_roots())
    wcsv(os.path.join(args.out, "placement_manifest.csv"), MANIFEST_FIELDS, rows)
    unused = [k for k in mapping if not used[k]]
    re_dec = collections.Counter(r["decision"] for r in rows if r["reason"].startswith("2b mapping"))
    print(f"remap: {len(mapping)} mapped groups; {sum(used.values())} holding files re-decided {dict(re_dec)}; "
          f"{len(unused)} mapped groups matched no holding file (raw-only, or a stale key)")
    for k in unused:
        print(f"    unmatched: {k} -> {mapping[k]}")
    for r in rows:
        if r["reason"].startswith("2b mapping") and r["decision"] != "place":
            print(f"  {r['decision']}: {r['project_name']} ({r['reason'][:80]})")
            break
    print(f"-> {os.path.join(args.out, 'placement_manifest.csv')}")
    return 0


def link_names_for(rows, raw_linked_dir, taken=None):
    """acq_id -> a link name unique in this project's raw_linked\\ -- the SAME rule the drives ingest
    used (ingest_plan.py, "link names: unique per project"): `<INSTR>_<name>`, then
    `<INSTR>_<stem>_<YYYYMMDD><ext>`, then `<INSTR>_<stem>_<ACQ-ID><ext>` (always unique). Without it
    raw_linked\\ (flat) collides on the many same-named files (`10x-1.czi`) -- the 2026-10-02 trial
    hit 404 collisions in two projects."""
    if taken is None:
        taken = {n.lower() for n in os.listdir(lp(raw_linked_dir))} if os.path.isdir(lp(raw_linked_dir)) else set()
    out = {}
    for r in sorted(rows, key=lambda r: (r.get("original_name") or "", r["acq_id"])):
        base = (r.get("original_name") or "").replace("\\", "/").split("/")[-1] or r["acq_id"]
        stem, ext = os.path.splitext(base)
        inst = r.get("instrument") or "RAW"
        day = (r.get("acquisition_datetime") or "")[:10].replace("-", "")
        for cand in (f"{inst}_{base}", f"{inst}_{stem}_{day}{ext}", f"{inst}_{stem}_{r['acq_id']}{ext}"):
            if cand.lower() not in taken:
                break
        taken.add(cand.lower())
        out[r["acq_id"]] = cand
    return out


def cmd_apply_raw(args):
    """2b, the RAW half: put each mapped group's blank-project acquisitions into Ryan's project.

    Reuses tools/manager/raw_import.py -- the Project Manager's "import from raw" engine -- so each
    acquisition gets exactly what ingest would have given it: a hard link in raw_linked/, a
    provenance row, and registry_raw.project_id set ONLY where it is still blank
    (set_project_id_if_blank). Nothing in /raw/ moves. Dry run (raw_import.plan) unless --execute;
    the plan per project is written to <out>\\apply_raw_<project>.csv either way. A project that does
    not exist or is closed is refused, never created or reopened here."""
    from manager import raw_import
    mapping = load_mapping(args.mapping)
    projects = load_projects(args.nas)
    reg = {r["acq_id"]: r for r in rd(os.path.join(args.nas, "registries", "registry_raw.csv"))}
    by_proj = collections.defaultdict(list)
    used = set()
    for a in it(os.path.join(args.repo, "tasks", "drives_blank_project_list.csv")):
        d, who, series, _kind = blank_list_group(a)
        nk = norm_key(key_string(d, who, series))
        if nk in mapping:
            by_proj[mapping[nk]].append(a["acq_id"])
            used.add(nk)
    print(f"{'EXECUTE' if args.execute else 'DRY RUN'}: {len(mapping)} mapped groups, {len(used)} with blank-project "
          f"acquisitions, {sum(len(v) for v in by_proj.values())} acquisitions into {len(by_proj)} projects")
    bad = 0
    for proj, ids in sorted(by_proj.items()):
        prow = projects.get(proj)
        if prow is None:
            print(f"  REFUSED {proj}: not in registry_projects.csv -- create it first (create_project.py)")
            bad += 1
            continue
        if (prow.get("status") or "").strip().lower() == "closed":
            print(f"  REFUSED {proj}: closed -- reopening is Ryan's call (reopen_project.py)")
            bad += 1
            continue
        rows = [reg[i] for i in ids if i in reg]
        missing = [i for i in ids if i not in reg]
        proj_dir = os.path.join(args.nas, "projects", project_folder(proj, projects))
        names = link_names_for(rows, os.path.join(proj_dir, "raw_linked"))
        pl = raw_import.plan(args.nas, prow, rows, link_names=names)
        wcsv(os.path.join(args.out, f"apply_raw_{proj}.csv"),
             ["acq_id", "status", "link_name", "raw_primary", "note", "existing_projects"],
             [dict(p, existing_projects=";".join(p["existing_projects"])) for p in pl])
        st = collections.Counter(p["status"] for p in pl)
        print(f"  {proj:28s} {len(ids):5d} acqs  {dict(st)}" + (f"  NOT IN REGISTRY: {len(missing)}" if missing else ""))
        if st.get(raw_import.ST_COLLISION) or st.get(raw_import.ST_NO_RAW) or missing:
            print(f"    -> resolve the collisions / missing rows in apply_raw_{proj}.csv before --execute")
            bad += 1
            continue
        if args.execute:
            todo = [reg[p["acq_id"]] for p in pl if p["status"] == raw_import.ST_NEW]
            res = raw_import.import_acquisitions(args.nas, prow, todo, args.by, link_names=names,
                                                 tool_name="nonraw_placement.py apply-raw")
            print(f"    {raw_import.summary_sentence(res)}")
    return 1 if bad else 0


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


NESTED_FARM = r"D:\projects\gjesus3\scratch_drives-nonraw-placement\farm_nested"


def cmd_nested_farm(args):
    """The nested-archive .czi that are NEW (nested_czi_dedup.csv verdict `NEW`) -> a farm on D: laid
    out as `<drive label>/<archive relpath>/<nested member path>/<inner path>` -- the same
    original_name convention the main ingest used for archive members (the `.zip` stays in the path)
    -- plus the per-file case table for tools/configs/drives_2026-10_dotfile/drives_nested.yaml.
    These are byte COPIES (a member cannot be hard-linked), verified against the hashed listing."""
    dd = [r for r in rd(args.dedup) if r["dedup"] == "NEW"]
    cases = []
    for r in dd:
        label = DRIVES[r["drive"]][0]
        orig = "/".join([label, r["archive"].replace("\\", "/"), r["nested"], r["inner"]])
        dst = os.path.join(NESTED_FARM, *orig.split("/"))
        if not (os.path.exists(lp(dst)) and sha256_file(dst) == r["sha256"]):
            outer = os.path.join(DRIVES[r["drive"]][1], "files", win(r["archive"]))
            with zipfile.ZipFile(lp(extract_nested(outer, r["nested"], args.scratch))) as z, z.open(r["inner"]) as src:
                os.makedirs(lp(os.path.dirname(dst)), exist_ok=True)
                with open(lp(dst), "wb") as out:
                    shutil.copyfileobj(src, out, 8 << 20)
        ok = sha256_file(dst) == r["sha256"]
        print(f"  {'ok ' if ok else 'BAD'} {orig}")
        if not ok:
            return 1
        name = os.path.basename(r["inner"])
        cases.append({"original_name": orig, "drv_project": "", "drv_researcher": "zuri", "drv_operator": "",
                      "drv_subject_alias": "", "drv_subject_animal": "", "drv_sample_id": name,
                      "drv_sample_type": "", "drv_link_name": f"{r['czi_instrument']}_{name}",
                      "drv_notes": ("Historical drive ingest 2026 (drive1_FRIO-X6); project / researcher / operator / "
                                    "subject decided per file before ingest (tasks/drives_ingest_dryrun_review.md). "
                                    "Claim: NO-CLAIM. Found inside a NESTED archive the first catalog never opened "
                                    "(tasks/drives_nonraw_placement_review.md); same rules as its batch-B05 siblings."),
                      "drv_sha256": r["sha256"], "drv_claim": "NO-CLAIM", "drv_acq_group": "", "drv_acq_group_n": ""})
    inst = {r["czi_instrument"] for r in dd}
    if inst != {"CELL"}:
        print(f"!! expected only CELL, got {inst}: the config is single-instrument")
        return 1
    path = os.path.join(args.repo, "tools", "configs", "drives_2026-10_dotfile", "cases_nested.csv")
    wcsv(path, list(cases[0].keys()), cases)
    print(f"{len(cases)} cases -> {path}")
    return 0


# ------------------------------------------------------------------------------------------ cli

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", default=OUT_DEFAULT)
    ap.add_argument("--nas", default=NAS_DEFAULT)
    ap.add_argument("--repo", default=os.path.dirname(os.path.dirname(HERE)))
    sub = ap.add_subparsers(dest="cmd", required=True)
    sp = sub.add_parser("plan")
    sp.add_argument("--roots", default=ROOTS_DEFAULT)
    sp.add_argument("--nmr", default=NMR_DEFAULT)
    sp.add_argument("--from-b", default=os.path.join(ANALYSIS, "drives-dicom", "nonraw_for_A.csv"))
    sp.add_argument("--nested", default=os.path.join(OUT_DEFAULT, "nested_members.csv"))
    sp.add_argument("--nested-dedup", default=os.path.join(OUT_DEFAULT, "nested_czi_dedup.csv"))
    sp.add_argument("--mapping", default=None,
                    help="2b: Ryan's filled-in worksheet; holding files of a mapped group are placed")
    sub.add_parser("dotfile-farm")
    sub.add_parser("nested").add_argument("--scratch", default=SCRATCH_DEFAULT)
    nf = sub.add_parser("nested-farm")
    nf.add_argument("--scratch", default=SCRATCH_DEFAULT)
    nf.add_argument("--dedup", default=os.path.join(OUT_DEFAULT, "nested_czi_dedup.csv"))
    ws = sub.add_parser("worksheet")
    ws.add_argument("--manifest", default=None)
    ws.add_argument("--force", action="store_true", help="overwrite a worksheet that has mapped groups")
    pa = sub.add_parser("paths")
    pa.add_argument("--manifest", default=None)
    pa.add_argument("--recompute-roots", nargs="*", default=[],
                    help="projects whose study folders are re-derived (e.g. after a rule change)")
    rm = sub.add_parser("remap")
    rm.add_argument("--manifest", default=os.path.join(OUT_DEFAULT, "placement_manifest.csv"),
                    help="the stored manifest (default: stream A's record; its copy off D: once D: is erased)")
    rm.add_argument("--mapping", required=True, help="Ryan's filled-in worksheet")
    ar = sub.add_parser("apply-raw")
    ar.add_argument("--mapping", required=True, help="Ryan's filled-in worksheet")
    ar.add_argument("--execute", action="store_true")
    ar.add_argument("--by", default=f"Data Office ({getpass.getuser()})")
    for name in ("copy", "verify", "holding"):
        s = sub.add_parser(name)
        s.add_argument("--manifest", default=None)
        s.add_argument("--project", nargs="*")
        s.add_argument("--execute", action="store_true")
        s.add_argument("--scratch", default=SCRATCH_DEFAULT)
        s.add_argument("--by", default=f"Data Office ({getpass.getuser()})")
        s.add_argument("--sample", type=float, default=0.02)
        s.add_argument("--seed", type=int, default=20261003)
        s.add_argument("--from-holding", action="store_true",
                       help="copy: read 2b-mapped files from the NAS holding folder instead of the D: staging")
    args = ap.parse_args(argv)
    if getattr(args, "manifest", None) is None:
        args.manifest = os.path.join(args.out, "placement_manifest.csv")
    os.makedirs(args.out, exist_ok=True)
    return {"plan": cmd_plan, "dotfile-farm": cmd_dotfile_farm, "nested": cmd_nested, "nested-farm": cmd_nested_farm, "worksheet": cmd_worksheet, "apply-raw": cmd_apply_raw, "remap": cmd_remap, "paths": cmd_paths, "copy": cmd_copy, "verify": cmd_verify, "holding": cmd_holding}[args.cmd](args) or 0


if __name__ == "__main__":
    sys.exit(main())
