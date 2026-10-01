#!/usr/bin/env python3
"""retire_acquisition.py -- retire an ACQ-ID: a Data-Office-only, backup-first, dry-run-first tool.

    python tools/retire_acquisition.py --nas-root "J:\\gjesus3-data" --acq-id ACQ-... --reason "..." \\
        (--duplicate-of ACQ-... | --derivative-of ACQ-... --to-project <name> [--subfolder outputs\\derived]
         | --orphan) [--execute]
    python tools/retire_acquisition.py --nas-root "J:\\gjesus3-data" --list retire_list.csv [--execute]

The default is a DRY RUN: it checks every precondition (hashing from disk) and prints exactly what
would change. Nothing is written without --execute.

WHAT "RETIRED" MEANS (Ryan, 2026-10-01; 06_REGISTRIES §2.9, 10_TOOLS §3.9). The acquisition's row LEAVES
registry_raw.csv and is appended, verbatim, to registries/retired_acquisitions.csv (the tombstone), with
the reason and what became of the bytes. The id is never reused. Three dispositions:
  duplicate   a second registration of bytes another LIVE acquisition (the survivor) already holds.
              Every file is re-hashed from disk on BOTH sides (checksums.json is never trusted alone: a
              production primary was found truncated with a checksums.json that matched the truncation).
              Only when every file is byte-identical are the /raw/ bytes deleted. A project link to the
              duplicate is re-pointed at the survivor (or removed, if the survivor is already linked there).
  derivative  a scale-bar copy, thumbnail or export registered as if it were an acquisition. It is hard-
              linked into its original's project folder (default subfolder outputs\\derived) as non-raw
              material, verified there by SHA-256, and only then leaves /raw/. Its raw_linked\\ links go.
  orphan      a /raw/ folder whose registry row was never written (a partial ingest). Backed up whole
              (it must be small), tombstoned without a row, deleted.
v1 does NOT re-identify a mis-coded acquisition (retire + re-register under the right instrument code); the
tombstone's disposition vocabulary is open for that (v2).

ORDER (a crash at any point is finished by re-running the same command; a re-run after success is a no-op):
  0. window: refuse while registries/.registry.lock exists or registry_raw.csv changed in the last 15 min
     (an ingest is running -- a batch ingest checks row counts and validator baselines and can restore
     backups; never retire inside its window).
  1. plan (read-only): classify each id (fresh / commit-interrupted / committed); check preconditions;
     hash; work out every link, row and file action. Any refusal stops the whole run before a write.
  2. backup: a FRESH dated off-NAS directory -- every registry CSV + .acq_id_seq.json, each retiree's
     metadata.json / checksums.json / README.txt, each touched project's provenance.csv (an orphan's whole
     folder) -- each copy verified by SHA-256. A duplicate's bytes are not backed up (verified identical to
     the survivor); a derivative's are moved, not lost.
  3. derivative only: hard-link the primary into the project subfolder; verify by identity + SHA-256.
  4. COMMIT, under the registry lock: append the tombstone (carrying every row about to be removed,
     verbatim); remove the registry_raw row; remove its ingest_manifest / pending_* rows; remove each
     registry_subjects row no other LIVE acquisition references. Every removal is byte-exact (all other
     bytes, line endings and quoting kept) and atomic (temp + os.replace), and read back to prove it.
  5. links, then bytes: re-point / remove project links (identity via file id, content via SHA-256 -- link
     counts read 1 over this SMB share, file ids do not lie); a duplicate is re-hashed against the survivor
     right before its folder is deleted; then the /raw/ folder goes. A link a researcher already deleted or
     renamed is reported, never an error (05_PROJECTS §3a). A link whose bytes are NOT the acquisition's
     (a researcher replaced the file) is left alone and reported.
  6. provenance: APPEND an event row per touched link / moved file to the project's provenance.csv.
  7. regenerate each touched project's index.html (generate_index.py --project).
  8. self-check + report (CSV + log) in the backup directory.

Exit codes: 0 done / no-op; 2 refused (nothing written); 3 backup failed (nothing else written);
4 failed mid-run (re-run to finish); 5 self-check failed.

Test hook: env RETIRE_FAIL_AFTER=<placed|tombstone|commit|links|bytes|provenance> raises right after that
step (crash-resume rehearsal only).
"""
import argparse
import csv
import datetime as dt
import getpass
import glob
import hashlib
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import time

TOOLS = os.path.dirname(os.path.abspath(__file__))
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)
from ingest import csv_safe, locking, pending, pending_dicom, pending_links  # noqa: E402
from ingest import project_ids as pids, projects_registry, provenance, registry, retired, subjects_table  # noqa: E402

CHUNK = 8 * 1024 * 1024
SIDECARS = ("metadata.json", "checksums.json", "README.txt")
RECENT_WRITE_WINDOW_S = 15 * 60
ORPHAN_MAX_BYTES = 50 * 1024 * 1024
DEFAULT_BACKUP_ROOT = r"C:\Users\rtasseff\temp"
DEFAULT_SUBFOLDER = "outputs/derived"
FAIL_AFTER = os.environ.get("RETIRE_FAIL_AFTER", "")
# acq_id-keyed bookkeeping an ingest writes (10_TOOLS §2.1 side-effect inventory #4, #6 + the two queues).
QUEUE_FILES = ("ingest_manifest.csv", pending.PENDING_FILENAME,
               pending_dicom.PENDING_DICOM_FILENAME, pending_links.PENDING_LINKS_FILENAME)


class Refused(Exception):
    """A precondition failed. Nothing has been written."""


def fail_point(step):
    if FAIL_AFTER == step:
        raise RuntimeError(f"injected failure after step '{step}' (RETIRE_FAIL_AFTER)")


# ---- filesystem helpers ---------------------------------------------------------------------------

def lp(path):
    """Long-path form for Windows file operations (paths past 260 chars exist under projects/)."""
    if os.name != "nt":
        return path
    p = os.path.abspath(path)
    if p.startswith("\\\\?\\"):
        return p
    if p.startswith("\\\\"):
        return "\\\\?\\UNC\\" + p[2:]
    return "\\\\?\\" + p


def exists(p):
    return os.path.lexists(lp(p))


def isdir(p):
    return os.path.isdir(lp(p))


def isfile(p):
    return os.path.isfile(lp(p))


_HASH_CACHE = {}


def sha256(path):
    """SHA-256 of a file, read fresh from disk (cached per run by path + size + mtime)."""
    st = os.stat(lp(path))
    key = (os.path.normcase(os.path.abspath(path)), st.st_size, st.st_mtime_ns)
    if key not in _HASH_CACHE:
        h = hashlib.sha256()
        with open(lp(path), "rb") as f:
            for b in iter(lambda: f.read(CHUNK), b""):
                h.update(b)
        _HASH_CACHE[key] = h.hexdigest()
    return _HASH_CACHE[key]


def samefile(a, b):
    try:
        return os.path.samefile(lp(a), lp(b))
    except OSError:
        return False


def tree_files(root):
    """{relative path: absolute path} for a file (key "") or every file under a folder."""
    if isfile(root):
        return {"": root}
    out = {}
    for dirpath, _dirs, files in os.walk(lp(root)):
        for fn in files:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, lp(root)).replace(os.sep, "/")
            out[rel] = os.path.join(root, rel.replace("/", os.sep))
    return out


def tree_digest(hashes):
    """One SHA-256 for a primary: the file's own hash, or (folder) the hash of "rel<TAB>sha\\n" lines."""
    if list(hashes) == [""]:
        return hashes[""]
    body = "".join(f"{k}\t{hashes[k]}\n" for k in sorted(hashes))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def tree_identity(link, primary):
    """'same' if every file of `link` is the same file (file id) as `primary`'s, else 'differs'."""
    a, b = tree_files(link), tree_files(primary)
    if set(a) != set(b) or not a:
        return "differs"
    return "same" if all(samefile(a[k], b[k]) for k in a) else "differs"


def tree_hashes(root):
    return {k: sha256(v) for k, v in tree_files(root).items()}


def remove_tree_or_file(path):
    def _onerror(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)   # a read-only attribute blocks delete on Windows
        func(p)
    if isdir(path):
        shutil.rmtree(lp(path), onerror=_onerror)
    elif exists(path):
        try:
            os.remove(lp(path))
        except PermissionError:
            os.chmod(lp(path), stat.S_IWRITE)
            os.remove(lp(path))


def link_tree(src, dest):
    """Hard-link `src` (file, or folder -> real folder of per-file links) at `dest`. Additive."""
    files = tree_files(src)
    if list(files) == [""]:
        if not exists(dest):
            os.makedirs(lp(os.path.dirname(dest)), exist_ok=True)
            os.link(lp(src), lp(dest))
        return
    for rel, s in files.items():
        d = os.path.join(dest, rel.replace("/", os.sep))
        if not exists(d):
            os.makedirs(lp(os.path.dirname(d)), exist_ok=True)
            os.link(lp(s), lp(d))


def repoint_tree(link, new_primary):
    """Make every file of `link` the same file as `new_primary`'s (temp link + os.replace, per file)."""
    target = tree_files(new_primary)
    for rel, s in target.items():
        d = link if rel == "" else os.path.join(link, rel.replace("/", os.sep))
        if exists(d) and samefile(d, s):
            continue
        tmp = d + ".retire-tmp"
        if exists(tmp):
            os.remove(lp(tmp))
        os.makedirs(lp(os.path.dirname(d)), exist_ok=True)
        os.link(lp(s), lp(tmp))
        os.replace(lp(tmp), lp(d))


def nas_abs(nas, nas_rel):
    parts = [p for p in (nas_rel or "").strip().strip("/").split("/") if p]
    return os.path.join(nas, *parts)


def nas_rel(nas, path):
    return "/" + os.path.relpath(path, nas).replace(os.sep, "/")


def raw_primary_path(nas, row):
    """The acquisition's primary (file, or <ACQ-ID>.data folder). Mirrors relink_projects.raw_primary_path."""
    acq_dir = nas_abs(nas, row.get("canonical_path", ""))
    primary = (row.get("primary_file_name") or "").strip()
    kind = (row.get("primary_kind") or "").strip()
    if primary and kind == "folder" and primary != row["acq_id"]:
        return os.path.join(acq_dir, primary.rstrip("/"))
    if primary and kind == "folder":
        return acq_dir
    if primary and not primary.endswith("/"):
        return os.path.join(acq_dir, primary)
    return acq_dir


def payload(nas, row):
    """{key: abs path} of an acquisition's bytes: its primary ("P" / "P/<rel>") and any other non-sidecar
    file in its folder ("extra/<rel>"). The three ingest sidecars are excluded (they name the ACQ-ID)."""
    acq_dir = nas_abs(nas, row.get("canonical_path", ""))
    prim = raw_primary_path(nas, row)
    out = {}
    for rel, absp in tree_files(acq_dir).items():
        full_norm = os.path.normcase(os.path.abspath(absp))
        prim_norm = os.path.normcase(os.path.abspath(prim))
        if "/" not in rel and rel in SIDECARS and full_norm != prim_norm:
            continue          # the ingest sidecars (even when the primary IS the acquisition folder)
        if full_norm == prim_norm:
            out["P"] = absp
        elif full_norm.startswith(prim_norm + os.sep):
            out["P/" + os.path.relpath(absp, prim).replace(os.sep, "/")] = absp
        else:
            out["extra/" + rel] = absp
    return out


# ---- registry helpers -----------------------------------------------------------------------------

def read_live(nas):
    return {(r.get("acq_id") or "").strip(): r
            for r in registry.read_registry(os.path.join(nas, "registries", "registry_raw.csv"))}


def subject_ids(row):
    return [s.strip() for s in (row.get("subject_ids") or "").split(";") if s.strip()]


def provenance_index(nas):
    """acq_id -> [(project_dir, prov_path, row)] for every provenance row naming it in input_refs."""
    idx = {}
    for prov in sorted(glob.glob(os.path.join(nas, "projects", "*", "provenance.csv"))):
        pdir = os.path.dirname(prov)
        with open(prov, "r", encoding="utf-8-sig", errors="replace", newline="") as f:
            for r in csv.DictReader(f):
                for acq in retired.ACQ_ID_RE.findall(r.get("input_refs") or ""):
                    idx.setdefault(acq, []).append((pdir, prov, r))
    return idx


def checksums_cover(acq_dir, hashes):
    """True if every fresh hash appears in the acquisition's checksums.json (text search, like
    repair_primary_inplace). None if there is no checksums.json."""
    p = os.path.join(acq_dir, "checksums.json")
    if not isfile(p):
        return None
    with open(lp(p), "rb") as f:
        text = f.read()
    return all(h.encode() in text for h in hashes.values())


# ---- the run --------------------------------------------------------------------------------------

class Run:
    def __init__(self, args):
        self.args = args
        self.nas = os.path.normpath(args.nas_root)
        self.reg_dir = os.path.join(self.nas, "registries")
        self.execute = args.execute
        self.run_id = "RET-" + dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]
        self.today = dt.date.today().isoformat()
        self.buf = io.StringIO()
        self.backup_dir = None

    def log(self, msg=""):
        print(msg)
        self.buf.write(msg + "\n")

    def load(self):
        self.live = read_live(self.nas)
        self.tombs = retired.read_retired(retired.retired_path(self.reg_dir))
        self.projects = projects_registry.read_projects(projects_registry.projects_registry_path(self.nas))
        self.citations = retired.curated_citations(self.nas)
        self.prov = provenance_index(self.nas)


def load_items(args):
    if args.list:
        items = []
        with open(args.list, "r", encoding="utf-8-sig", newline="") as f:
            for i, r in enumerate(csv.DictReader(f), start=2):
                items.append({
                    "acq_id": (r.get("acq_id") or "").strip(),
                    "disposition": (r.get("disposition") or "").strip().lower(),
                    "target": (r.get("target_acq_id") or "").strip(),
                    "to_project": (r.get("to_project") or "").strip(),
                    "subfolder": (r.get("subfolder") or "").strip() or DEFAULT_SUBFOLDER,
                    "dest_name": (r.get("dest_name") or "").strip(),
                    "reason": (r.get("reason") or "").strip(),
                    "line": i,
                })
        return items
    disp = "duplicate" if args.duplicate_of else "derivative" if args.derivative_of else \
        "orphan" if args.orphan else ""
    return [{"acq_id": args.acq_id, "disposition": disp,
             "target": args.duplicate_of or args.derivative_of or "",
             "to_project": args.to_project or "", "subfolder": args.subfolder or DEFAULT_SUBFOLDER,
             "dest_name": args.dest_name or "", "reason": (args.reason or "").strip(), "line": None}]


def find_project(run, name_or_id):
    p = projects_registry.find_project(run.projects, name_or_id)
    return p


def project_of_folder(run, folder_abs):
    for p in run.projects:
        loc = (p.get("folder_location") or "").strip()
        if loc and os.path.normcase(nas_abs(run.nas, loc)) == os.path.normcase(folder_abs):
            return p
    return None


def safe_subfolder(sub):
    sub = sub.replace("\\", "/").strip("/")
    parts = [p for p in sub.split("/") if p]
    if not parts or any(p in (".", "..") for p in parts) or ":" in sub or parts[0].lower() == "raw_linked":
        raise Refused(f"--subfolder {sub!r} must be a relative path inside the project, not raw_linked")
    return "/".join(parts)


def plan_item(run, it, run_retirees, run_targets):
    """Work out everything for one id. Raises Refused. Read-only (hashes from disk unless --quick)."""
    acq = it["acq_id"]
    quick = run.args.quick
    if not retired.ACQ_ID_RE.fullmatch(acq or ""):
        raise Refused(f"{acq!r} is not an ACQ-ID")
    live, tomb = acq in run.live, run.tombs.get(acq)
    p = {"acq_id": acq, "item": it, "warnings": [], "info": [], "actions": [], "links": [],
         "hashes_verified": False}

    # ---- state ----
    if tomb and not live:
        p["state"] = "committed"
    elif tomb and live:
        p["state"] = "commit-interrupted"
    elif live:
        p["state"] = "fresh"
    else:
        p["state"] = "orphan-candidate"

    if tomb:
        # A tombstoned id follows ITS record, not the arguments.
        disp, target = tomb["disposition"], (tomb.get("superseded_by") or "").strip()
        if (it["disposition"], it["target"]) != (disp, target):
            p["warnings"].append(f"already tombstoned as {disp} of {target or '-'}; the arguments "
                                 f"({it['disposition']} of {it['target'] or '-'}) are ignored")
        p["disposition"], p["target"] = disp, target
        p["reason"] = tomb.get("reason", "")
        p["row"] = run.live.get(acq) or retired.original_row(tomb, registry.REGISTRY_FIELDS)
        p["sha256"] = tomb.get("sha256", "")
    else:
        disp, target = it["disposition"], it["target"]
        if disp not in retired.DISPOSITIONS:
            raise Refused(f"{acq}: disposition must be one of {retired.DISPOSITIONS}, got {disp!r}")
        if not it["reason"]:
            raise Refused(f"{acq}: --reason is required")
        p["disposition"], p["target"], p["reason"] = disp, target, it["reason"]
        if disp == "orphan":
            if live:
                raise Refused(f"{acq} has a registry row: it is not an orphan")
        elif not live:
            raise Refused(f"{acq} is not in registry_raw.csv and not tombstoned")
        p["row"] = run.live.get(acq, {})

    # ---- references that must not break ----
    cited = run.citations.get(acq)
    if cited and not tomb:
        raise Refused(f"{acq} is cited by a curated dataset: {'; '.join(cited)}")
    chained = sorted(a for a, t in run.tombs.items() if (t.get("superseded_by") or "").strip() == acq)
    if chained:
        raise Refused(f"{acq} is the superseded_by of tombstone(s) {', '.join(chained)}; retiring it "
                      f"would break the chain")
    if acq in run_targets:
        raise Refused(f"{acq} is the survivor/original of another item in this run")
    if p["disposition"] == "orphan":
        return plan_orphan(run, p, tomb)
    if not target or target == acq:
        raise Refused(f"{acq}: needs a different {'survivor' if disp == 'duplicate' else 'original'}")
    if target not in run.live:
        raise Refused(f"{acq}: {target} is not a live acquisition"
                      + (" (it is retired)" if target in run.tombs else ""))
    if target in run_retirees:
        raise Refused(f"{acq}: {target} is itself being retired in this run")

    row = p["row"]
    p["acq_dir"] = nas_abs(run.nas, row.get("canonical_path", ""))
    p["primary"] = raw_primary_path(run.nas, row)
    p["raw_present"] = isdir(p["acq_dir"])
    trow = run.live[target]
    p["target_row"] = trow
    p["target_primary"] = raw_primary_path(run.nas, trow)
    if not exists(p["target_primary"]):
        raise Refused(f"{acq}: the {target} primary is missing on disk: {p['target_primary']}")

    if p["disposition"] == "duplicate":
        plan_duplicate(run, p, quick)
    else:
        plan_derivative(run, p, it, tomb, quick)
    plan_links(run, p)
    plan_rows(run, p)
    return p


def plan_duplicate(run, p, quick):
    acq, target = p["acq_id"], p["target"]
    tpay = payload(run.nas, p["target_row"])
    if p["raw_present"]:
        pay = payload(run.nas, p["row"])
        if set(pay) != set(tpay):
            raise Refused(f"{acq}: file sets differ from {target}: only in {acq}: "
                          f"{sorted(set(pay) - set(tpay))}; only in {target}: {sorted(set(tpay) - set(pay))}")
        for k in pay:
            sa, sb = os.path.getsize(lp(pay[k])), os.path.getsize(lp(tpay[k]))
            if sa != sb:
                raise Refused(f"{acq}: {k} is {sa} bytes, {target}'s is {sb}: not a byte-identical "
                              f"duplicate (a re-save? -- v1 refuses; see the review)")
        if quick:
            p["info"].append(f"QUICK: sizes match on {len(pay)} file(s); hashes NOT checked")
        else:
            ha = {k: sha256(v) for k, v in pay.items()}
            hb = {k: sha256(v) for k, v in tpay.items()}
            diff = [k for k in ha if ha[k] != hb[k]]
            if diff:
                raise Refused(f"{acq}: {len(diff)} file(s) differ from {target} by SHA-256 ({diff[:3]}): "
                              f"not a duplicate (a re-save? -- v1 refuses; see the review)")
            tcov = checksums_cover(nas_abs(run.nas, p["target_row"]["canonical_path"]),
                                   {k: v for k, v in hb.items() if k.startswith("P")})
            if tcov is False:
                raise Refused(f"{acq}: the survivor {target}'s bytes do not match its own checksums.json "
                              f"-- investigate it (truncation?) before retiring a twin into it")
            if checksums_cover(p["acq_dir"], {k: v for k, v in ha.items() if k.startswith("P")}) is False:
                p["warnings"].append(f"{acq}'s checksums.json does not match its bytes (the bytes match "
                                     f"the survivor, which matches its own)")
            prim = {k[2:] if k.startswith("P/") else "": v for k, v in ha.items() if k.startswith("P")}
            p["sha256"] = tree_digest(prim)
            p["hashes_verified"] = True
            p["info"].append(f"SHA-256 identical to {target} on all {len(pay)} file(s) ({p['sha256'][:12]})")
        p["actions"].append(f"delete /raw/ folder {p['acq_dir']}")
    else:
        p["info"].append("/raw/ folder already deleted")
        if not p.get("sha256"):
            p["sha256"] = tree_digest(tree_hashes(p["target_primary"]))


def plan_derivative(run, p, it, tomb, quick):
    acq = p["acq_id"]
    if tomb:
        moved = (tomb.get("moved_to") or "").strip()
        if not moved:
            raise Refused(f"{acq}: tombstoned as a derivative without moved_to -- fix by hand")
        p["dest"] = nas_abs(run.nas, moved)
        proj = project_of_folder(run, nas_abs(run.nas, "/".join(moved.strip("/").split("/")[:2])))
        p["to_project"] = proj
        if not exists(p["dest"]):
            raise Refused(f"{acq}: the moved file {p['dest']} is missing -- the derivative's bytes may be "
                          f"only in /raw/ ({p['acq_dir']}); investigate before re-running")
    else:
        proj = find_project(run, it["to_project"])
        if not it["to_project"] or not proj:
            raise Refused(f"{acq}: --to-project {it['to_project']!r} is not in registry_projects.csv")
        if (proj.get("status") or "").strip() == "closed":
            raise Refused(f"{acq}: project {proj['name']} is closed. Projects are reopened case by case "
                          f"(tools/reopen_project.py); then re-run")
        pdir = nas_abs(run.nas, proj.get("folder_location", ""))
        if not isdir(pdir):
            raise Refused(f"{acq}: project folder {pdir} does not exist")
        orig_projects = pids.split_project_ids(p["target_row"].get("project_id"))
        if proj["project_id"] not in orig_projects:
            p["warnings"].append(f"{proj['project_id']} is not the original {p['target']}'s project "
                                 f"({';'.join(orig_projects) or 'none'})")
        sub = safe_subfolder(it["subfolder"])
        name = it["dest_name"] or os.path.basename(
            (p["row"].get("original_name") or "").replace("\\", "/").rstrip("/")) \
            or os.path.basename(p["primary"])
        if not name or name in (".", "..") or "/" in name or "\\" in name:
            raise Refused(f"{acq}: no safe destination name (pass --dest-name)")
        p["to_project"] = proj
        p["dest"] = os.path.join(pdir, *sub.split("/"), name)
    if p["raw_present"]:
        pay = payload(run.nas, p["row"])
        extras = [k for k in pay if k.startswith("extra/")]
        if extras:
            raise Refused(f"{acq}: /raw/ folder holds files besides the primary and sidecars ({extras}); "
                          f"they would be lost -- investigate")
        if not exists(p["primary"]):
            raise Refused(f"{acq}: primary missing: {p['primary']}")
        if exists(p["dest"]):
            if tree_identity(p["dest"], p["primary"]) != "same":
                raise Refused(f"{acq}: {p['dest']} already exists and is not this file (pass --dest-name)")
            p["info"].append(f"already placed at {nas_rel(run.nas, p['dest'])}")
        else:
            p["actions"].append(f"hard-link the primary to {nas_rel(run.nas, p['dest'])} and verify")
        if not quick:
            prim = tree_hashes(p["primary"])
            p["sha256"] = tree_digest(prim)
            p["hashes_verified"] = True
            cov = checksums_cover(p["acq_dir"], prim)
            if cov is False:
                p["warnings"].append(f"{acq}'s checksums.json does not match its bytes; the bytes are "
                                     f"moved as they are")
        p["actions"].append(f"delete /raw/ folder {p['acq_dir']}")
    else:
        p["info"].append("/raw/ folder already deleted")
        if not p.get("sha256"):
            p["sha256"] = tree_digest(tree_hashes(p["dest"]))


def plan_orphan(run, p, tomb):
    acq = p["acq_id"]
    date = acq.split("-")[1]
    hits = glob.glob(os.path.join(run.nas, "raw", "*", date[:4], f"{date[:4]}-{date[4:6]}", acq))
    if tomb:
        p["acq_dir"] = nas_abs(run.nas, tomb.get("original_canonical_path", ""))
        p["raw_present"] = isdir(p["acq_dir"])
        if p["raw_present"]:
            p["actions"].append(f"delete orphan folder {p['acq_dir']} (backed up first)")
        else:
            p["info"].append("orphan folder already deleted")
    else:
        if len(hits) != 1:
            raise Refused(f"{acq}: expected exactly one /raw/ folder, found {len(hits)}: {hits}")
        p["acq_dir"] = hits[0]
        p["raw_present"] = True
        if run.prov.get(acq):
            raise Refused(f"{acq}: a project provenance row references it -- not a plain orphan")
        size = sum(os.path.getsize(lp(v)) for v in tree_files(p["acq_dir"]).values())
        if size > ORPHAN_MAX_BYTES:
            raise Refused(f"{acq}: orphan folder is {size / 1e6:.1f} MB; only small placeholders "
                          f"(<= {ORPHAN_MAX_BYTES / 1e6:.0f} MB) are retired as orphans")
        h = tree_hashes(p["acq_dir"])
        p["sha256"] = tree_digest(h)
        p["hashes_verified"] = True
        p["info"].append(f"orphan folder {nas_rel(run.nas, p['acq_dir'])}: {len(h)} file(s), "
                         f"{size / 1e6:.2f} MB")
        p["actions"].append(f"delete orphan folder {p['acq_dir']} (backed up first)")
    p["row"] = {}
    p["links"] = []
    plan_rows(run, p)
    return p


def plan_links(run, p):
    """Every project link to the retiree (found through provenance input_refs), and what to do with it."""
    acq, dup = p["acq_id"], p["disposition"] == "duplicate"
    seen = set()
    for pdir, prov, r in run.prov.get(acq, []):
        out = (r.get("output_path") or "").strip().replace("\\", "/")
        if not out.startswith("raw_linked/") or (r.get("file_type") or "").startswith("hardlink-removed"):
            continue
        path = os.path.join(pdir, *out.split("/"))
        key = os.path.normcase(path)
        if key in seen:
            continue
        seen.add(key)
        L = {"project_dir": pdir, "prov": prov, "output_path": out, "path": path}
        removed_ev = {"output_path": out, "notes": _tag(p, "link-removed")}
        if not exists(path) and prov_has(prov, removed_ev):
            L["action"], L["done_as"], L["why"] = "done", "remove", "removed by an earlier run"
        elif not exists(path):
            L["action"], L["why"] = "absent", "already deleted or renamed (researcher-owned folder)"
        elif dup:
            if tree_identity(path, p["target_primary"]) == "same":
                L["action"], L["why"] = "done", f"already the survivor {p['target']}"
            elif (p["raw_present"] and tree_identity(path, p["primary"]) == "same") or \
                    (not p["raw_present"] and _content_is(path, p["target_primary"])):
                other = _survivor_link_in(run, pdir, p)
                if other:
                    L["action"], L["why"] = "remove", f"{p['target']} is already linked here as {other}"
                else:
                    L["action"], L["why"] = "replace", f"re-point at the survivor {p['target']} (same bytes)"
            else:
                L["action"], L["why"] = "foreign", "the file there is not this acquisition's bytes; left alone"
        else:
            if p["raw_present"] and tree_identity(path, p["primary"]) == "same":
                L["action"], L["why"] = "remove", f"now lives at {nas_rel(run.nas, p['dest'])}"
            elif exists(p["dest"]) and tree_identity(path, p["dest"]) == "same":
                L["action"], L["why"] = "remove", f"now lives at {nas_rel(run.nas, p['dest'])}"
            else:
                L["action"], L["why"] = "foreign", "the file there is not this acquisition's bytes; left alone"
        p["links"].append(L)


def _content_is(path, primary):
    a, b = tree_files(path), tree_files(primary)
    return set(a) == set(b) and all(sha256(a[k]) == sha256(b[k]) for k in a)


def _survivor_link_in(run, pdir, p):
    """The output_path under which the survivor is already linked in this project, if any."""
    for d, _prov, r in run.prov.get(p["target"], []):
        if os.path.normcase(d) != os.path.normcase(pdir):
            continue
        out = (r.get("output_path") or "").strip().replace("\\", "/")
        path = os.path.join(d, *out.split("/"))
        if out.startswith("raw_linked/") and exists(path) and \
                tree_identity(path, p["target_primary"]) == "same":
            return out
    return None


def plan_rows(run, p):
    """Rows the commit will remove (or, once committed, still has to remove)."""
    acq = p["acq_id"]
    rows = {}
    if acq in run.live:
        rows["registry_raw.csv"] = 1
    for fn in QUEUE_FILES:
        path = os.path.join(run.reg_dir, fn)
        n = len(csv_safe.remove_records(path, "acq_id", {acq}, dry_run=True))
        if n:
            rows[fn] = n
    subj = unreferenced_subjects(run, p)
    if subj:
        rows["registry_subjects.csv"] = len(subj)
    p["subjects_to_remove"] = subj
    p["rows"] = rows
    p["subjects_kept"] = [s for s in subject_ids(p["row"]) if s not in subj]


def unreferenced_subjects(run, p, live=None):
    live = run.live if live is None else live
    mine = subject_ids(p.get("row") or {})
    if not mine:
        return []
    others = set()
    for aid, r in live.items():
        if aid != p["acq_id"]:
            others.update(subject_ids(r))
    present = subjects_table.read_subjects(subjects_table.subjects_path(run.reg_dir))
    return [s for s in mine if s not in others and s in present]


def has_work(p):
    return bool(p["actions"] or p["rows"] or p["state"] in ("fresh", "commit-interrupted", "orphan-candidate")
                or any(L["action"] in ("replace", "remove") for L in p["links"])
                or missing_events(p))


def missing_events(p):
    out = []
    for L in p["links"]:
        if L["action"] in ("replace", "remove", "done", "absent"):
            ev = event_row(p, L)
            if ev and not prov_has(L["prov"], ev):
                out.append((L["prov"], ev))
    if p["disposition"] == "derivative" and p.get("to_project"):
        prov = os.path.join(nas_abs(p["_nas"], p["to_project"]["folder_location"]), "provenance.csv")
        ev = moved_event(p)
        if not prov_has(prov, ev):
            out.append((prov, ev))
    return out


# ---- provenance events ---------------------------------------------------------------------------

def _tag(p, event):
    return f"retire_acquisition: {p['acq_id']} {event}"


def event_row(p, L):
    acq, tgt = p["acq_id"], p["target"]
    sv = provenance.software_version_string("retire_acquisition.py")
    base = {"output_path": L["output_path"], "output_name": L["output_path"].split("/")[-1],
            "date_created": p["_today"], "creator": p["_by"], "software_version": sv,
            "parameters_ref": p["_run_id"], "lab_notebook_ref": ""}
    done_state = L.get("done_as", L["action"])
    if done_state in ("replace", "done") and p["disposition"] == "duplicate":
        return dict(base, file_type="hardlink", input_refs=tgt, notes=_tag(p, "replaced-by " + tgt),
                    process_description=f"Re-pointed by retire_acquisition.py: {acq} was retired as a "
                                        f"duplicate of {tgt} (byte-identical); this link now points at {tgt}")
    if done_state == "remove":
        what = (f"retired as a duplicate of {tgt}, which is already linked in this project"
                if p["disposition"] == "duplicate"
                else f"retired as a derivative of {tgt}; moved to {nas_rel(p['_nas'], p['dest'])}")
        return dict(base, file_type="hardlink-removed", input_refs=acq, notes=_tag(p, "link-removed"),
                    process_description=f"Removed by retire_acquisition.py: {acq} {what}")
    if done_state == "absent":
        return dict(base, file_type="hardlink-removed", input_refs=acq, notes=_tag(p, "retired"),
                    process_description=f"{acq} retired by retire_acquisition.py ({p['disposition']} of "
                                        f"{tgt}); this link was already gone (removed or renamed in the "
                                        f"project) and was not touched")
    return None


def moved_event(p):
    rel = os.path.relpath(p["dest"], nas_abs(p["_nas"], p["to_project"]["folder_location"])).replace(os.sep, "/")
    return {"output_path": rel, "output_name": os.path.basename(p["dest"]),
            "file_type": os.path.splitext(p["dest"])[1] or "folder",
            "date_created": p["_today"], "creator": p["_by"], "input_refs": p["target"],
            "process_description": f"Moved out of /raw/ by retire_acquisition.py: {p['acq_id']} was a "
                                   f"derivative of {p['target']} (not an acquisition) and was retired; "
                                   f"the same bytes now live here as non-raw material",
            "software_version": provenance.software_version_string("retire_acquisition.py"),
            "parameters_ref": p["_run_id"], "lab_notebook_ref": "", "notes": _tag(p, "moved-to")}


def prov_has(prov, ev):
    if not os.path.exists(prov):
        return False
    with open(prov, "r", encoding="utf-8-sig", errors="replace", newline="") as f:
        return any((r.get("output_path") or "").strip() == ev["output_path"]
                   and (r.get("notes") or "").strip() == ev["notes"] for r in csv.DictReader(f))


# ---- execute steps -------------------------------------------------------------------------------

def take_backup(run, plans):
    bk = os.path.join(run.args.backup_root, f"gjesus3_retire_backup_{run.run_id[4:]}")
    if os.path.exists(bk):
        raise RuntimeError(f"backup dir {bk} already exists")
    os.makedirs(bk)
    srcs = sorted(glob.glob(os.path.join(run.reg_dir, "*.csv")))
    seq = os.path.join(run.reg_dir, ".acq_id_seq.json")
    if os.path.exists(seq):
        srcs.append(seq)
    pairs = [(s, os.path.join(bk, "registries", os.path.basename(s))) for s in srcs]
    provs = set()
    for p in plans:
        acq_dir = p.get("acq_dir")
        if p["disposition"] == "orphan" and acq_dir and isdir(acq_dir):
            for rel, s in tree_files(acq_dir).items():
                pairs.append((s, os.path.join(bk, "acquisitions", p["acq_id"], *rel.split("/"))))
        elif acq_dir and isdir(acq_dir):
            for sc in SIDECARS:
                s = os.path.join(acq_dir, sc)
                if isfile(s):
                    pairs.append((s, os.path.join(bk, "acquisitions", p["acq_id"], sc)))
        provs.update(L["prov"] for L in p["links"])
        if p.get("to_project"):
            provs.add(os.path.join(nas_abs(run.nas, p["to_project"]["folder_location"]), "provenance.csv"))
    for prov in sorted(provs):
        if os.path.exists(prov):
            name = os.path.basename(os.path.dirname(prov))
            pairs.append((prov, os.path.join(bk, "projects", name, "provenance.csv")))
    manifest = []
    for s, d in pairs:
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.copy2(lp(s), d)
        hs, hd = sha256(s), sha256(d)
        if hs != hd:
            raise RuntimeError(f"backup of {s} does not verify")
        manifest.append((s, d, hs))
    with open(os.path.join(bk, "backup_manifest.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["source", "backup", "sha256"])
        w.writerows(manifest)
    run.backup_dir = bk
    run.log(f"backup: {bk} ({len(manifest)} files, every copy SHA-256-verified)")


def place_derivative(run, p):
    if not p["raw_present"] or "dest" not in p:
        return
    if not exists(p["dest"]):
        link_tree(p["primary"], p["dest"])
    if tree_identity(p["dest"], p["primary"]) != "same":
        raise RuntimeError(f"{p['acq_id']}: {p['dest']} is not the raw primary after linking")
    got = tree_digest(tree_hashes(p["dest"]))
    if p.get("sha256") and got != p["sha256"]:
        raise RuntimeError(f"{p['acq_id']}: placed file hashes {got}, expected {p['sha256']}")
    p["sha256"] = got
    run.log(f"  placed {nas_rel(run.nas, p['dest'])} (same file as the primary; SHA-256 {got[:12]})")
    prov = os.path.join(nas_abs(run.nas, p["to_project"]["folder_location"]), "provenance.csv")
    provenance.append_entry(prov, moved_event(p), unique_on=("output_path", "notes"))


def commit(run, p):
    """The commit point. Under the registry lock; every removal byte-exact, atomic and read back."""
    acq = p["acq_id"]
    raw_csv = os.path.join(run.reg_dir, "registry_raw.csv")
    subj_csv = subjects_table.subjects_path(run.reg_dir)
    with locking.registry_lock(run.reg_dir):
        registry.assert_header_compatible(raw_csv)
        live = read_live(run.nas)
        tombs = retired.read_retired(retired.retired_path(run.reg_dir))
        if acq not in tombs:
            if p["disposition"] != "orphan" and acq not in live:
                raise RuntimeError(f"{acq} vanished from registry_raw.csv during the run")
            if p["disposition"] != "orphan":
                p["row"] = live[acq]
            raw_rec = csv_safe.remove_records(raw_csv, "acq_id", {acq}, dry_run=True)
            others = {}
            for fn in QUEUE_FILES:
                recs = csv_safe.remove_records(os.path.join(run.reg_dir, fn), "acq_id", {acq}, dry_run=True)
                if recs:
                    others[fn] = [r.decode("utf-8", "replace").rstrip("\r\n") for r in recs]
            subj = unreferenced_subjects(run, p, live=live)
            if subj:
                recs = csv_safe.remove_records(subj_csv, "facility_id", set(subj), dry_run=True)
                others["registry_subjects.csv"] = [r.decode("utf-8", "replace").rstrip("\r\n") for r in recs]
            retired.append_retired(retired.retired_path(run.reg_dir), {
                "acq_id": acq, "retired_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "disposition": p["disposition"], "superseded_by": p["target"], "reason": p["reason"],
                "bytes_fate": "moved" if p["disposition"] == "derivative" else "deleted",
                "moved_to": nas_rel(run.nas, p["dest"]) if p["disposition"] == "derivative" else "",
                "sha256": p.get("sha256", ""),
                "original_canonical_path": (p["row"].get("canonical_path") if p["row"]
                                            else nas_rel(run.nas, p["acq_dir"]) + "/"),
                "retired_by": run.args.retired_by, "run_id": run.run_id,
                "backup_dir": run.backup_dir or "",
                "registry_raw_row": raw_rec[0].decode("utf-8").rstrip("\r\n") if raw_rec else "",
                "other_rows_removed": json.dumps(others, ensure_ascii=False, sort_keys=True),
            })
            run.log(f"  tombstone: appended ({p['disposition']} of {p['target'] or '-'})")
            fail_point("tombstone")
        n_raw = len(csv_safe.remove_records(raw_csv, "acq_id", {acq}))
        removed = {"registry_raw.csv": n_raw} if n_raw else {}
        for fn in QUEUE_FILES:
            n = len(csv_safe.remove_records(os.path.join(run.reg_dir, fn), "acq_id", {acq}))
            if n:
                removed[fn] = n
        # Recompute against the registry as it is NOW (the retiree's row is gone).
        live_now = read_live(run.nas)
        subj = unreferenced_subjects(run, p, live=live_now)
        if subj:
            subjects_table.assert_header_compatible(subj_csv)
            removed["registry_subjects.csv"] = len(csv_safe.remove_records(subj_csv, "facility_id", set(subj)))
        p["subjects_removed"] = subj
    run.log(f"  commit: removed rows {removed or '{}'}; subjects kept (still referenced): "
            f"{p.get('subjects_kept') or '-'}")
    p["rows_removed"] = removed
    fail_point("commit")


def do_links(run, p):
    """Re-point / remove links. The provenance event is appended FIRST (write-ahead): a crash between
    the event and the action leaves the link in place, and the re-run completes the action against the
    event that already describes it -- so the record never says "a researcher removed it" when this
    tool did."""
    for L in p["links"]:
        if L["action"] in ("replace", "remove"):
            ev = event_row(p, dict(L, done_as=L["action"]))
            provenance.append_entry(L["prov"], ev, unique_on=("output_path", "notes"))
        if L["action"] == "replace":
            repoint_tree(L["path"], p["target_primary"])
            if tree_identity(L["path"], p["target_primary"]) != "same":
                raise RuntimeError(f"{L['path']} is not the survivor after re-pointing")
            if not _content_is(L["path"], p["target_primary"]):
                raise RuntimeError(f"{L['path']} does not hash as the survivor after re-pointing")
            L["done_as"] = "replace"
            run.log(f"  link re-pointed: {nas_rel(run.nas, L['path'])} -> {p['target']}")
        elif L["action"] == "remove":
            remove_tree_or_file(L["path"])
            if exists(L["path"]):
                raise RuntimeError(f"{L['path']} still exists after removal")
            L["done_as"] = "remove"
            run.log(f"  link removed: {nas_rel(run.nas, L['path'])} ({L['why']})")
        elif L["action"] in ("absent", "foreign"):
            run.log(f"  link {L['action']}: {nas_rel(run.nas, L['path'])} -- {L['why']}")
    fail_point("links")


def do_bytes(run, p):
    if not p.get("raw_present") or not isdir(p["acq_dir"]):
        return
    acq = p["acq_id"]
    if p["disposition"] == "duplicate":
        # Re-verify right before the delete, from disk, unless this run already hashed both sides.
        if not p["hashes_verified"]:
            pay, tpay = payload(run.nas, p["row"]), payload(run.nas, p["target_row"])
            if set(pay) != set(tpay) or any(sha256(pay[k]) != sha256(tpay[k]) for k in pay):
                raise RuntimeError(f"{acq}: no longer byte-identical to {p['target']} -- NOT deleted")
    elif p["disposition"] == "derivative":
        if tree_identity(p["dest"], p["primary"]) != "same" or \
                tree_digest(tree_hashes(p["dest"])) != p["sha256"]:
            raise RuntimeError(f"{acq}: {p['dest']} does not verify -- /raw/ NOT deleted")
    remove_tree_or_file(p["acq_dir"])
    if exists(p["acq_dir"]):
        raise RuntimeError(f"{p['acq_dir']} still exists after delete")
    run.log(f"  /raw/ folder deleted: {nas_rel(run.nas, p['acq_dir'])}")
    fail_point("bytes")


def do_provenance(run, p):
    n = 0
    for prov, ev in missing_events(p):
        if provenance.append_entry(prov, ev, unique_on=("output_path", "notes")):
            n += 1
    if n:
        run.log(f"  provenance: {n} event row(s) appended")
    fail_point("provenance")
    return n


def touched_projects(run, p):
    ids = set(pids.split_project_ids((p.get("row") or {}).get("project_id")))
    for L in p["links"]:
        proj = project_of_folder(run, L["project_dir"])
        if proj:
            ids.add(proj["project_id"])
    if p.get("to_project"):
        ids.add(p["to_project"]["project_id"])
    return ids


def regen_indexes(run, project_ids):
    open_ids = [i for i in sorted(project_ids)
                if (find_project(run, i) or {}).get("status", "").strip() != "closed"]
    if not open_ids or run.args.no_index:
        if open_ids:
            run.log(f"index: skipped (--no-index) for {', '.join(open_ids)}")
        return
    cmd = [sys.executable, os.path.join(TOOLS, "generate_index.py"), "--nas-root", run.nas]
    for i in open_ids:
        cmd += ["--project", i]
    rc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    tail = (rc.stdout or rc.stderr or "").strip().splitlines()[-1:] or [""]
    run.log(f"index: regenerated {', '.join(open_ids)} (rc={rc.returncode}) {tail[0]}")
    if rc.returncode:
        run.log("WARN: index regeneration failed; re-run generate_index.py --project by hand")


def self_check(run, plans):
    live = read_live(run.nas)
    tombs = retired.read_retired(retired.retired_path(run.reg_dir))
    problems = []
    for p in plans:
        acq = p["acq_id"]
        if acq not in tombs:
            problems.append(f"{acq}: not in the tombstone file")
        if acq in live:
            problems.append(f"{acq}: still in registry_raw.csv")
        if p.get("acq_dir") and isdir(p["acq_dir"]):
            problems.append(f"{acq}: /raw/ folder still present")
        for L in p["links"]:
            done = L.get("done_as", L["action"])
            if done in ("replace", "done") and tree_identity(L["path"], p["target_primary"]) != "same":
                problems.append(f"{acq}: {L['path']} is not the survivor")
            if done == "remove" and exists(L["path"]):
                problems.append(f"{acq}: {L['path']} still exists")
        if p["disposition"] == "derivative":
            if not exists(p["dest"]) or tree_digest(tree_hashes(p["dest"])) != tombs.get(acq, {}).get("sha256"):
                problems.append(f"{acq}: moved file missing or not the tombstoned SHA-256")
        if missing_events(p):
            problems.append(f"{acq}: provenance events missing")
    return problems


# ---- main ----------------------------------------------------------------------------------------

def window_check(run):
    lock = os.path.join(run.reg_dir, locking.LOCK_FILENAME)
    raw = os.path.join(run.reg_dir, "registry_raw.csv")
    msgs = []
    if os.path.exists(lock):
        msgs.append(f"{lock} exists: an ingest (or another registry writer) is running")
    age = time.time() - os.path.getmtime(raw) if os.path.exists(raw) else 1e9
    if age < RECENT_WRITE_WINDOW_S and not run.args.allow_recent_registry_writes:
        msgs.append(f"registry_raw.csv changed {age / 60:.1f} min ago: an ingest may be mid-batch "
                    f"(never retire inside an ingest's window; --allow-recent-registry-writes overrides "
                    f"once you have confirmed none is running)")
    return msgs


def describe(run, p):
    it = p["item"]
    head = f"{p['acq_id']}  [{p['state']}]  {p['disposition']}"
    if p["target"]:
        head += f" of {p['target']}"
    run.log(head)
    for m in p["info"]:
        run.log(f"    info: {m}")
    for m in p["warnings"]:
        run.log(f"    WARN: {m}")
    for a in p["actions"]:
        run.log(f"    will: {a}")
    if p["rows"]:
        run.log(f"    will: remove rows {p['rows']} (registry_subjects only for subjects no live "
                f"acquisition references; kept: {p.get('subjects_kept') or '-'})")
    for L in p["links"]:
        run.log(f"    link: {L['action']:8s} {nas_rel(run.nas, L['path'])} -- {L['why']}")
    ev = missing_events(p)
    if ev:
        run.log(f"    will: append {len(ev)} provenance event row(s)")
    if has_work(p) and touched_projects(run, p):
        run.log(f"    will: regenerate index.html for {sorted(touched_projects(run, p))}")
    if not has_work(p):
        run.log("    no-op: already fully retired")


def write_report(run, plans, results):
    path = os.path.join(run.backup_dir, f"{run.run_id}_report.csv")
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["acq_id", "disposition", "superseded_by", "state_before", "result", "sha256",
                    "moved_to", "rows_removed", "subjects_removed", "subjects_kept", "links", "message"])
        for p in plans:
            res, msg = results.get(p["acq_id"], ("", ""))
            w.writerow([p["acq_id"], p["disposition"], p["target"], p["state"], res, p.get("sha256", ""),
                        nas_rel(run.nas, p["dest"]) if p.get("dest") else "",
                        json.dumps(p.get("rows_removed", {})), ";".join(p.get("subjects_removed", [])),
                        ";".join(p.get("subjects_kept", [])),
                        "; ".join(f"{L.get('done_as', L['action'])}:{L['output_path']}@"
                                  f"{os.path.basename(L['project_dir'])}" for L in p["links"]), msg])
    with open(os.path.join(run.backup_dir, f"{run.run_id}.log"), "w", encoding="utf-8") as f:
        f.write(run.buf.getvalue())
    print(f"report: {path}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--nas-root", required=True)
    ap.add_argument("--acq-id")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--duplicate-of", metavar="ACQ-ID", help="the surviving (live) acquisition")
    g.add_argument("--derivative-of", metavar="ACQ-ID", help="the original (live) acquisition")
    g.add_argument("--orphan", action="store_true", help="a /raw/ folder with no registry row")
    ap.add_argument("--to-project", help="derivative: the project (name or PROJ-ID) to move it into")
    ap.add_argument("--subfolder", default=DEFAULT_SUBFOLDER, help="derivative: inside the project")
    ap.add_argument("--dest-name", help="derivative: file name in the subfolder (default: its original name)")
    ap.add_argument("--reason")
    ap.add_argument("--list", help="CSV: acq_id,disposition,target_acq_id,to_project,reason[,subfolder,dest_name]")
    ap.add_argument("--execute", action="store_true", help="write (default: dry run)")
    ap.add_argument("--quick", action="store_true", help="dry run only: compare sizes, skip hashing")
    ap.add_argument("--retired-by", default=getpass.getuser(), help="who is running this (Data Office)")
    ap.add_argument("--backup-root", default=DEFAULT_BACKUP_ROOT, help="off-NAS directory for the backup")
    ap.add_argument("--allow-recent-registry-writes", action="store_true")
    ap.add_argument("--no-index", action="store_true", help="skip index.html regeneration (tests)")
    args = ap.parse_args(argv)
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    if bool(args.list) == bool(args.acq_id):
        ap.error("give exactly one of --acq-id or --list")
    if args.acq_id and not (args.duplicate_of or args.derivative_of or args.orphan):
        ap.error("--acq-id needs --duplicate-of, --derivative-of or --orphan")
    if args.execute and args.quick:
        ap.error("--quick is for dry runs; --execute always hashes")

    run = Run(args)
    if not os.path.isdir(run.reg_dir):
        print(f"REFUSED: {run.nas} has no registries/ folder")
        return 2
    tag = "" if run.execute else "[dry-run] "
    run.log(f"{tag}retire_acquisition {run.run_id} on {run.nas}")
    win = window_check(run)
    for m in win:
        run.log(("REFUSED: " if run.execute else "WARN: ") + m)
    if win and run.execute:
        return 2

    run.load()
    items = load_items(args)
    ids = [i["acq_id"] for i in items]
    dupes = sorted({a for a in ids if ids.count(a) > 1})
    if dupes:
        run.log(f"REFUSED: listed more than once: {dupes}")
        return 2
    run_retirees = set(ids)
    plans, refusals = [], []
    for it in items:
        try:
            others = {i["target"] for i in items if i is not it and i["target"]}
            p = plan_item(run, it, run_retirees, others)
            p["_nas"], p["_today"], p["_by"], p["_run_id"] = run.nas, run.today, args.retired_by, run.run_id
            plans.append(p)
        except Refused as ex:
            refusals.append(str(ex))
    for p in plans:
        describe(run, p)
    if refusals:
        for r in refusals:
            run.log(f"REFUSED: {r}")
        run.log(f"{tag}{len(refusals)} refusal(s): nothing written")
        return 2
    work = [p for p in plans if has_work(p)]
    run.log(f"{tag}{len(plans)} item(s): {len(work)} with work, {len(plans) - len(work)} already done")
    if not run.execute:
        run.log("[dry-run] nothing written. Re-run with --execute to apply.")
        return 0
    if not work:
        run.log("no-op: everything listed is already retired")
        return 0

    try:
        take_backup(run, work)
    except Exception as ex:  # noqa: BLE001 -- reported; nothing else has been written
        run.log(f"STOP: backup failed: {type(ex).__name__}: {ex}")
        return 3

    results, touched, failed = {}, set(), False
    for p in work:
        run.log(f"{p['acq_id']}:")
        try:
            if p["disposition"] == "derivative":
                place_derivative(run, p)
                fail_point("placed")
            if p["state"] != "committed" or p["rows"]:
                commit(run, p)
            do_links(run, p)
            do_bytes(run, p)
            do_provenance(run, p)
            touched |= touched_projects(run, p)
            results[p["acq_id"]] = ("done", "")
        except Exception as ex:  # noqa: BLE001 -- counted; the run stops so a re-run can resume
            results[p["acq_id"]] = ("error", f"{type(ex).__name__}: {ex}")
            run.log(f"  ERROR: {type(ex).__name__}: {ex}")
            run.log("STOP: re-run the same command to finish (every step resumes from what is on disk)")
            failed = True
            break
    regen_indexes(run, touched)
    problems = [] if failed else self_check(run, [p for p in work if results.get(p["acq_id"], ("",))[0] == "done"])
    for m in problems:
        run.log(f"SELF-CHECK FAILED: {m}")
    if not failed and not problems:
        run.log(f"self-check: OK for {len(results)} item(s)")
    write_report(run, plans, results)
    return 4 if failed else 5 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
