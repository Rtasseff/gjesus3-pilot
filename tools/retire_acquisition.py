#!/usr/bin/env python3
"""retire_acquisition.py -- retire an ACQ-ID: a Data-Office-only, backup-first, dry-run-first tool.

    python tools/retire_acquisition.py --nas-root "J:\\gjesus3-data" --acq-id ACQ-... --reason "..." \\
        (--duplicate-of ACQ-... | --equivalent-of ACQ-... | --derivative-of ACQ-... --to-project <name>
         [--subfolder outputs\\derived] | --orphan | --reidentify-as <CODE> [--instrument-model "..."])
        [--execute]
    python tools/retire_acquisition.py --nas-root "J:\\gjesus3-data" --list retire_list.csv [--execute]

The default is a DRY RUN: it checks every precondition (hashing from disk) and prints exactly what
would change. Nothing is written without --execute.

WHAT "RETIRED" MEANS (Ryan, 2026-10-01; 06_REGISTRIES §2.9, 10_TOOLS §3.9). The acquisition's row LEAVES
registry_raw.csv and is appended, verbatim, to registries/retired_acquisitions.csv (the tombstone), with
the reason and what became of the bytes. The id is never reused. Five dispositions:
  duplicate   a second registration of bytes another LIVE acquisition (the survivor) already holds.
              Every file is re-hashed from disk on BOTH sides (checksums.json is never trusted alone: a
              production primary was found truncated with a checksums.json that matched the truncation).
              Only when every file is byte-identical are the /raw/ bytes deleted. A project link to the
              duplicate is re-pointed at the survivor (or removed, if the survivor is already linked there).
  equivalent  (v2) a .czi re-save: NOT byte-identical to the survivor, but the same information -- the
              metadata XML, every subblock's decoded pixels (with its position, metadata and attachments)
              and every attachment's payload are identical (ingest/czi_compare.py). The comparison is the
              evidence, recorded in the tombstone's reason. Then handled like a duplicate.
  derivative  a scale-bar copy, thumbnail or export registered as if it were an acquisition. It is hard-
              linked into its original's project folder (default subfolder outputs\\derived) as non-raw
              material, verified there by SHA-256, and only then leaves /raw/. Its raw_linked\\ links go.
  orphan      a /raw/ folder whose registry row was never written (a partial ingest). Backed up whole
              (it must be small), tombstoned without a row, deleted.
  reidentified (v2) a mis-coded acquisition (the wrong instrument code, so the wrong ACQ-ID), re-registered
              IN PLACE under the right code: a new ACQ-ID from the normal allocator; the new /raw/ folder
              gets a HARD LINK to the same file (so every project link stays valid -- nothing is copied);
              its metadata.json / checksums.json / README.txt are rewritten byte-exactly except the id and
              the instrument (ingest/reidentify.py); the old folder is then removed. The file's OWN device
              fingerprint must name the new code. superseded_by = the new id. No re-ingest, so the ingest's
              dedup index is never consulted (and the source stays blocked from a re-ingest afterwards).

ORDER (a crash at any point is finished by re-running the same command; a re-run after success is a no-op):
  0. window: refuse while registries/.registry.lock exists or registry_raw.csv changed in the last 15 min
     (an ingest is running -- a batch ingest checks row counts and validator baselines and can restore
     backups; never retire inside its window).
  1. plan (read-only): classify each id (fresh / commit-interrupted / committed); check preconditions;
     hash; work out every link, row and file action. Any refusal stops the whole run before a write.
  2. backup: a FRESH dated off-NAS directory -- every registry CSV + .acq_id_seq.json, each retiree's
     metadata.json / checksums.json / README.txt, each touched project's provenance.csv (an orphan's whole
     folder) -- each copy verified by SHA-256. A duplicate's bytes are not backed up (verified identical to
     the survivor); a derivative's are moved, not lost; a re-identified file is never removed at all.
  3. derivative only: hard-link the primary into the project subfolder; verify by identity + SHA-256.
  4. COMMIT, under the registry lock: append the tombstone (carrying every row about to be removed,
     verbatim); remove the registry_raw row; remove its ingest_manifest / pending_* rows. Every removal
     is byte-exact (all other bytes, line endings and quoting kept) and atomic (temp + os.replace), and
     read back to prove it. registry_subjects.csv is NEVER touched: subjects are never deleted (06 §2.8.3,
     Ryan 2026-10-01) -- an animal existed whether or not gjesus3 keeps its acquisition.
     reidentified splits it: COMMIT A (allocate the new id; append the tombstone -- the durable record of
     it; the old row stays live) -> BUILD the new folder (link + rewritten sidecars, each verified) ->
     COMMIT B (append the new row and the carried-over manifest / pending rows; then remove the old ones).
     The registry never points a live row at a folder that does not exist.
  5. links, then bytes: re-point / remove project links (identity via file id, content via SHA-256 -- link
     counts read 1 over this SMB share, file ids do not lie); a duplicate is re-hashed against the survivor
     right before its folder is deleted; then the /raw/ folder goes. A link a researcher already deleted or
     renamed is reported, never an error (05_PROJECTS §3a). A link whose bytes are NOT the acquisition's
     (a researcher replaced the file) is left alone and reported. A re-identified acquisition's links are
     not touched at all (same file); each gets an event naming its new id.
  6. provenance: APPEND an event row per touched link / moved file to the project's provenance.csv.
  7. regenerate each touched project's index.html (generate_index.py --project).
  8. self-check + report (CSV + log) in the backup directory.

Exit codes: 0 done / no-op; 2 refused (nothing written); 3 backup failed (nothing else written);
4 failed mid-run (re-run to finish); 5 self-check failed.

Test hook: env RETIRE_FAIL_AFTER=<placed|tombstone|built|commit|links|bytes|provenance> raises right after
that step (crash-resume rehearsal only).
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
import re
import shutil
import stat
import subprocess
import sys
import time
from collections import Counter

TOOLS = os.path.dirname(os.path.abspath(__file__))
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)
from ingest import acq_id as acq_mod, czi_compare, reidentify  # noqa: E402
from ingest import csv_safe, locking, pending, pending_dicom, pending_links  # noqa: E402
from ingest import project_ids as pids, projects_registry, provenance, registry, retired  # noqa: E402

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
DUPLICATE_LIKE = ("duplicate", "equivalent")
FILE_READONLY = 0x1      # stat.FILE_ATTRIBUTE_READONLY (Windows)


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


def read_bytes(p):
    with open(lp(p), "rb") as f:
        return f.read()


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


def remove_link_name(path, survivor):
    """Remove ONE name of a file that lives on under `survivor` (another hard link to the same file).

    Attributes are per FILE, shared by every link: clearing a read-only attribute to delete this name
    would clear it on the survivor and on every project link too. So it is cleared only when the delete
    needs it, and then restored on the survivor.
    """
    try:
        os.remove(lp(path))
        return
    except PermissionError:
        attrs = getattr(os.stat(lp(path)), "st_file_attributes", 0)
        if not attrs & FILE_READONLY:
            raise
    os.chmod(lp(path), stat.S_IWRITE)
    try:
        os.remove(lp(path))
    finally:
        os.chmod(lp(survivor), stat.S_IREAD)


def write_verified(path, data):
    """Write bytes through a temp file + os.replace (fsync), then read back. A no-op if already equal."""
    if isfile(path) and read_bytes(path) == data:
        return False
    tmp = path + ".retire-tmp"
    with open(lp(tmp), "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(lp(tmp), lp(path))
    if read_bytes(path) != data:
        raise RuntimeError(f"{path} does not read back as written")
    return True


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


def czi_fingerprint(path):
    """The instrument a .czi's OWN metadata names (tools/reference/microscopy_instruments.yaml rules,
    applied by tools/drive_staging/catalog.py). Returns (dict, None) or (None, reason)."""
    ds = os.path.join(TOOLS, "drive_staging")
    if ds not in sys.path:
        sys.path.insert(0, ds)
    import catalog  # noqa: E402 -- the drive catalog owns the fingerprint rules
    xml, err = catalog.czi_read_xml(path)
    if xml is None:
        return None, err
    try:
        meta = catalog.parse_czi_xml(xml)
    except Exception as ex:  # noqa: BLE001 -- reported as the reason
        return None, f"metadata XML unparseable: {ex}"
    inst, rule, fired = catalog.fingerprint(catalog.load_instruments(), meta["serials"], meta["keys"],
                                            meta["stand"])
    return {"instrument": inst, "rule": rule, "fired": [list(f) for f in fired],
            "serials": meta["serials"], "stand_keys": meta["keys"], "stand": meta["stand"]}, None


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
        self._preview = {}

    def log(self, msg=""):
        print(msg)
        self.buf.write(msg + "\n")

    def load(self):
        self.live = read_live(self.nas)
        self.tombs = retired.read_retired(retired.retired_path(self.reg_dir))
        self.projects = projects_registry.read_projects(projects_registry.projects_registry_path(self.nas))
        self.citations = retired.curated_citations(self.nas)
        self.prov = provenance_index(self.nas)

    def preview_new_id(self, date, code):
        """The id a re-identify WOULD get (dry run): live + tombstoned + reserved high-water, plus one per
        earlier re-identify to the same prefix in this run. The real one is allocated at commit A."""
        prefix = f"ACQ-{date}-{code}-"
        if prefix not in self._preview:
            hi = 0
            for a in list(self.live) + list(self.tombs):
                if a.startswith(prefix):
                    try:
                        hi = max(hi, int(a.rsplit("-", 1)[1]))
                    except ValueError:
                        pass
            try:
                res = int(acq_mod._read_reservations(self.reg_dir).get(prefix, 0))
            except (TypeError, ValueError):
                res = 0
            self._preview[prefix] = max(hi, res)
        self._preview[prefix] += 1
        return f"{prefix}{self._preview[prefix]:03d}"


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
                    "new_instrument": (r.get("new_instrument") or "").strip(),
                    "instrument_model": (r.get("instrument_model") or "").strip(),
                    "reason": (r.get("reason") or "").strip(),
                    "line": i,
                })
        return items
    disp = "duplicate" if args.duplicate_of else "equivalent" if args.equivalent_of else \
        "derivative" if args.derivative_of else "orphan" if args.orphan else \
        "reidentified" if args.reidentify_as else ""
    return [{"acq_id": args.acq_id, "disposition": disp,
             "target": args.duplicate_of or args.equivalent_of or args.derivative_of or "",
             "to_project": args.to_project or "", "subfolder": args.subfolder or DEFAULT_SUBFOLDER,
             "dest_name": args.dest_name or "", "new_instrument": args.reidentify_as or "",
             "instrument_model": args.instrument_model or "",
             "reason": (args.reason or "").strip(), "line": None}]


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


def _rel_word(disposition):
    return "as" if disposition == "reidentified" else "of"


def plan_item(run, it, run_retirees, run_targets):
    """Work out everything for one id. Raises Refused. Read-only (hashes from disk unless --quick)."""
    acq = it["acq_id"]
    quick = run.args.quick
    if not retired.ACQ_ID_RE.fullmatch(acq or ""):
        raise Refused(f"{acq!r} is not an ACQ-ID")
    live, tomb = acq in run.live, run.tombs.get(acq)
    p = {"acq_id": acq, "item": it, "warnings": [], "info": [], "actions": [], "links": [],
         "hashes_verified": False, "rows_add": {}}

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
        asked = (it["disposition"], it["target"])
        have = (disp, target)
        if disp == "reidentified":
            asked = (it["disposition"], (it.get("new_instrument") or "").upper())
            have = (disp, target.split("-")[2] if target.count("-") == 3 else target)
        if asked != have:
            p["warnings"].append(f"already tombstoned as {disp} {_rel_word(disp)} {target or '-'}; the "
                                 f"arguments ({it['disposition']} {it['target'] or it.get('new_instrument') or '-'})"
                                 f" are ignored")
        p["disposition"], p["target"] = disp, target
        p["reason"] = tomb.get("reason", "")
        p["row"] = run.live.get(acq) or retired.original_row(tomb, registry.REGISTRY_FIELDS)
        p["sha256"] = tomb.get("sha256", "")
        p["retired_at"] = tomb.get("retired_at", "")
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
        if disp == "reidentified" and target:
            raise Refused(f"{acq}: a re-identify takes the new instrument code (new_instrument / "
                          f"--reidentify-as), not a target_acq_id")
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
    if p["disposition"] == "reidentified":
        plan_reidentify(run, p, it, tomb, quick)
        plan_links(run, p)
        plan_rows(run, p)
        return p
    if not target or target == acq:
        raise Refused(f"{acq}: needs a different {'survivor' if disp in DUPLICATE_LIKE else 'original'}")
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
    elif p["disposition"] == "equivalent":
        plan_equivalent(run, p, quick)
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
                              f"duplicate (a re-save? -- see --equivalent-of)")
        if quick:
            p["info"].append(f"QUICK: sizes match on {len(pay)} file(s); hashes NOT checked")
        else:
            ha = {k: sha256(v) for k, v in pay.items()}
            hb = {k: sha256(v) for k, v in tpay.items()}
            diff = [k for k in ha if ha[k] != hb[k]]
            if diff:
                raise Refused(f"{acq}: {len(diff)} file(s) differ from {target} by SHA-256 ({diff[:3]}): "
                              f"not a duplicate (a re-save? -- see --equivalent-of)")
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


def _is_single_czi(row):
    return ((row.get("primary_kind") or "").strip() == "file"
            and (row.get("file_format") or "").strip().lower() == ".czi")


def equivalence(retiree_path, survivor_path):
    """(differences, evidence) of two .czi primaries -- the whole content comparison, from disk."""
    sa = czi_compare.signature(retiree_path)
    sb = czi_compare.signature(survivor_path)
    diffs = czi_compare.compare(sa, sb)
    ev = czi_compare.evidence(sa, sb, sha256(retiree_path), sha256(survivor_path))
    return diffs, ev


def plan_equivalent(run, p, quick):
    """A .czi re-save: same information as the survivor, different container (retire tool v2)."""
    acq, target = p["acq_id"], p["target"]
    for r, who in ((p["row"], acq), (p["target_row"], target)):
        if not _is_single_czi(r):
            raise Refused(f"{who}: content-equivalence is defined for single-file .czi acquisitions only "
                          f"({r.get('primary_kind')} {r.get('file_format')})")
    if (p["row"].get("instrument") or "") != (p["target_row"].get("instrument") or ""):
        p["info"].append(f"instrument codes differ ({p['row'].get('instrument')} vs "
                         f"{p['target_row'].get('instrument')}): the survivor's is kept")
    if (p["row"].get("acquisition_datetime") or "") != (p["target_row"].get("acquisition_datetime") or ""):
        p["warnings"].append(f"acquisition_datetime differs in the registry ({p['row'].get('acquisition_datetime')} "
                             f"vs {p['target_row'].get('acquisition_datetime')}) although the metadata is compared")
    if not p["raw_present"]:
        p["info"].append("/raw/ folder already deleted")
        return
    pay = payload(run.nas, p["row"])
    extras = sorted(k for k in pay if k != "P")
    if extras:
        raise Refused(f"{acq}: /raw/ folder holds files besides the primary and sidecars ({extras}); "
                      f"they would be lost -- investigate")
    if "P" not in pay:
        raise Refused(f"{acq}: primary missing: {p['primary']}")
    sa, sb = os.path.getsize(lp(p["primary"])), os.path.getsize(lp(p["target_primary"]))
    if quick:
        p["info"].append(f"QUICK: {sa:,} vs {sb:,} bytes; content NOT compared")
    else:
        ha, hb = sha256(p["primary"]), sha256(p["target_primary"])
        if ha == hb:
            raise Refused(f"{acq}: byte-identical to {target} -- retire it with --duplicate-of instead")
        tdir = nas_abs(run.nas, p["target_row"]["canonical_path"])
        if checksums_cover(tdir, {"": hb}) is False:
            raise Refused(f"{acq}: the survivor {target}'s bytes do not match its own checksums.json "
                          f"-- investigate it (truncation?) before retiring a re-save into it")
        if checksums_cover(p["acq_dir"], {"": ha}) is False:
            p["warnings"].append(f"{acq}'s checksums.json does not match its bytes (they are compared as "
                                 f"they are)")
        try:
            diffs, ev = equivalence(p["primary"], p["target_primary"])
        except Exception as ex:  # noqa: BLE001 -- an unreadable .czi is a refusal, not a crash
            raise Refused(f"{acq}: cannot compare the .czi content: {type(ex).__name__}: {ex}")
        if diffs:
            raise Refused(f"{acq}: not content-equivalent to {target}: " + "; ".join(diffs[:5]))
        p["sha256"], p["target_sha256"], p["evidence"] = ha, hb, ev
        p["hashes_verified"] = True
        c = ev["retiree"], ev["survivor"]
        p["info"].append(
            f"content-equivalent to {target}: metadata XML ({ev['metadata_xml_chars']:,} chars), "
            f"{ev['subblocks']} subblock(s) decoded and {len(ev['attachments'])} attachment(s) identical; "
            f"container differs: {c[0]['bytes']:,} vs {c[1]['bytes']:,} bytes, DELETED segments "
            f"{c[0]['deleted_bytes']:,} vs {c[1]['deleted_bytes']:,} bytes")
    p["actions"].append(f"delete /raw/ folder {p['acq_dir']}")


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


# ---- re-identify (v2) -----------------------------------------------------------------------------

def _set_new_paths(run, p):
    ch = p["changes"]
    p["new_dir"] = nas_abs(run.nas, ch["canonical_path"][1])
    p["new_primary"] = os.path.join(p["new_dir"], ch["primary_file_name"][1])


def new_sidecars(p, date):
    """The new folder's three sidecars: the old ones, rewritten byte-exactly (ingest/reidentify.py)."""
    old, new, ch = p["acq_id"], p["target"], p["changes"]
    old_code, new_code = ch["instrument"]
    om, nm = ch.get("instrument_model", [None, None])
    rule = (p.get("fingerprint") or {}).get("rule", "device metadata")

    def rd(name):
        return read_bytes(os.path.join(p["acq_dir"], name))
    return {
        "metadata.json": reidentify.rewrite_metadata_json(rd("metadata.json"), old, new, old_code, new_code),
        "checksums.json": reidentify.rewrite_checksums_json(rd("checksums.json"), old, new,
                                                            ch["primary_file_name"][1], p.get("sha256") or None),
        "README.txt": reidentify.rewrite_readme(rd("README.txt"), old, new, old_code, new_code,
                                                reidentify.readme_note(old, old_code, new_code, date, rule),
                                                om, nm),
    }


def plan_reidentify(run, p, it, tomb, quick):
    """A mis-coded acquisition re-registered in place under the right instrument code (retire tool v2)."""
    acq, row = p["acq_id"], p["row"]
    if not row:
        raise Refused(f"{acq}: its registry row cannot be read back from the tombstone -- fix by hand")
    p["acq_dir"] = nas_abs(run.nas, row.get("canonical_path", ""))
    p["primary"] = raw_primary_path(run.nas, row)
    p["raw_present"] = isdir(p["acq_dir"])
    if tomb:
        _reason, ev = retired.split_evidence(tomb.get("reason", ""))
        changes = (ev or {}).get("changes")
        if (not p["target"] or not isinstance(changes, dict)
                or (changes.get("acq_id") or [None, None])[1] != p["target"]):
            raise Refused(f"{acq}: tombstoned as reidentified, but the tombstone does not carry its new id "
                          f"and field changes -- fix by hand")
        p["evidence"], p["changes"] = ev, changes
        p["new_code"] = reidentify.instrument_of(p["target"])
        p["fingerprint"] = ev.get("fingerprint") or {}
    else:
        old_code = (row.get("instrument") or "").strip()
        new_code = (it.get("new_instrument") or "").strip().upper()
        if not re.fullmatch(r"[A-Z0-9]+", new_code):
            raise Refused(f"{acq}: {it.get('new_instrument')!r} is not an instrument code")
        if new_code == old_code:
            raise Refused(f"{acq}: it is already {old_code}")
        if old_code != acq.split("-")[2]:
            raise Refused(f"{acq}: its row says instrument {old_code!r}, its ACQ-ID says {acq.split('-')[2]!r} "
                          f"-- investigate")
        eco = (row.get("data_ecosystem") or "").strip()
        in_use = {(r.get("instrument") or "").strip() for r in run.live.values()
                  if (r.get("data_ecosystem") or "").strip() == eco}
        if new_code not in in_use:
            raise Refused(f"{acq}: {new_code} is not an instrument code in use in {eco} (a typo?)")
        if not _is_single_czi(row):
            raise Refused(f"{acq}: v2 re-identifies single-file .czi acquisitions only "
                          f"({row.get('primary_kind')} {row.get('file_format')})")
        model = (it.get("instrument_model") or "").strip() or None
        p["model_arg"] = model
        p["new_code"] = new_code
        p["target"] = run.preview_new_id(acq.split("-")[1], new_code)
        try:
            p["changes"] = reidentify.changes_for(row, p["target"], model)
        except ValueError as ex:
            raise Refused(f"{acq}: {ex}")
        models = Counter((r.get("instrument_model") or "").strip() for r in run.live.values()
                         if (r.get("instrument") or "").strip() == new_code)
        keep = (p["changes"].get("instrument_model") or [None, row.get("instrument_model", "")])[1]
        if models and keep not in models:
            p["warnings"].append(f"live {new_code} rows use instrument_model "
                                 f"{models.most_common(1)[0][0]!r}; this row keeps {keep!r} "
                                 f"(pass --instrument-model to change it)")
        p["info"].append(f"new id (preview; allocated at execute): {p['target']}")
    _set_new_paths(run, p)
    p["new_present"] = isdir(p["new_dir"])
    p["new_live"] = p["target"] in run.live
    p["new_sidecars"] = None

    old_complete = p["raw_present"] and isfile(p["primary"]) and \
        all(isfile(os.path.join(p["acq_dir"], s)) for s in SIDECARS)
    if p["raw_present"] and tomb and not old_complete:
        # A run stopped inside the old folder's delete (one name of the file or a sidecar already gone).
        # Finish it only if the new folder is complete and registered.
        if not (p["new_live"] and new_folder_complete(p, p.get("sha256"))):
            raise Refused(f"{acq}: the old folder is partly deleted and the new one ({p['new_dir']}) is not "
                          f"complete -- investigate (backup: {tomb.get('backup_dir')})")
        if exists(p["primary"]) and not samefile(p["primary"], p["new_primary"]):
            raise Refused(f"{acq}: {p['primary']} is not the same file as {p['new_primary']} -- investigate")
        p["partial_old"] = True
        p["info"].append("the old folder is partly deleted; the new one is complete")
        p["actions"].append(f"delete the rest of the old /raw/ folder {p['acq_dir']}")
        return
    if p["raw_present"]:
        pay = payload(run.nas, row)
        extras = sorted(k for k in pay if k != "P")
        if extras:
            raise Refused(f"{acq}: /raw/ folder holds files besides the primary and sidecars ({extras}); "
                          f"they would be lost -- investigate")
        if "P" not in pay or not isfile(p["primary"]):
            raise Refused(f"{acq}: primary missing: {p['primary']}")
        missing = [s for s in SIDECARS if not isfile(os.path.join(p["acq_dir"], s))]
        if missing:
            raise Refused(f"{acq}: sidecar(s) missing: {missing} -- investigate")
        if not tomb:
            fp, err = czi_fingerprint(p["primary"])
            if fp is None:
                raise Refused(f"{acq}: cannot read the .czi's own device metadata ({err})")
            if len(fp["fired"]) > 1:
                raise Refused(f"{acq}: the device fingerprint is ambiguous ({fp['fired']}) -- investigate")
            if fp["instrument"] != p["new_code"]:
                raise Refused(f"{acq}: the file's own device metadata says {fp['instrument']} ({fp['rule']}), "
                              f"not {p['new_code']}")
            p["fingerprint"] = fp
            p["info"].append(f"device fingerprint: {fp['instrument']} ({fp['rule']}; stand {fp['stand']!r})")
        if quick:
            p["info"].append("QUICK: primary NOT hashed")
        else:
            h = sha256(p["primary"])
            if checksums_cover(p["acq_dir"], {"": h}) is not True:
                raise Refused(f"{acq}: the primary's SHA-256 ({h[:12]}) is not in its checksums.json -- "
                              f"investigate before re-registering these bytes")
            if tomb and p.get("sha256") and p["sha256"] != h:
                raise Refused(f"{acq}: the primary hashes {h[:12]}, its tombstone says {p['sha256'][:12]}")
            p["sha256"] = h
            p["hashes_verified"] = True
            p["info"].append(f"primary SHA-256 {h[:12]} matches its checksums.json")
        if p["new_present"]:
            if not tomb:
                raise Refused(f"{acq}: the new folder {p['new_dir']} already exists -- investigate")
            if exists(p["new_primary"]) and not samefile(p["new_primary"], p["primary"]):
                raise Refused(f"{acq}: {p['new_primary']} exists and is NOT the same file as the primary "
                              f"-- investigate")
        try:
            # Validates the rewrite now (refuse before any write); rebuilt with the real id at execute.
            p["new_sidecars"] = new_sidecars(p, (p.get("retired_at") or run.today)[:10])
        except (ValueError, OSError) as ex:
            raise Refused(f"{acq}: its sidecars cannot be rewritten safely: {ex}")
        if not (p["new_present"] and exists(p["new_primary"])):
            p["actions"].append(f"hard-link the primary as {nas_rel(run.nas, p['new_primary'])} (the same file: "
                                f"every project link stays valid; nothing is copied)")
        p["actions"].append("write the new metadata.json / checksums.json / README.txt (id and instrument "
                            "rewritten, every other byte kept)")
        p["actions"].append(f"delete the old /raw/ folder {p['acq_dir']} (one name of the file and its three "
                            f"sidecars; the file lives on as {p['target']})")
    else:
        if not tomb:
            raise Refused(f"{acq}: its /raw/ folder {p['acq_dir']} is missing")
        if not (p["new_present"] and isfile(p["new_primary"])):
            raise Refused(f"{acq}: the old folder is gone and the new one ({p['new_dir']}) is incomplete -- "
                          f"investigate (backup: {tomb.get('backup_dir')})")
        p["info"].append("old /raw/ folder already deleted")


def plan_links(run, p):
    """Every project link to the retiree (found through provenance input_refs), and what to do with it."""
    acq, disp = p["acq_id"], p["disposition"]
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
        if disp == "reidentified":
            primary = p["primary"] if p["raw_present"] and exists(p["primary"]) else p["new_primary"]
            if not exists(path):
                L["action"], L["why"] = "absent", "already deleted or renamed (researcher-owned folder)"
            elif tree_identity(path, primary) == "same":
                L["action"], L["why"] = "keep", f"the same file: now {p['target']}, nothing to change"
            else:
                L["action"], L["why"] = "foreign", "the file there is not this acquisition's bytes; left alone"
        elif not exists(path) and prov_has(prov, removed_ev):
            L["action"], L["done_as"], L["why"] = "done", "remove", "removed by an earlier run"
        elif not exists(path):
            L["action"], L["why"] = "absent", "already deleted or renamed (researcher-owned folder)"
        elif disp in DUPLICATE_LIKE:
            gone_but_still_here = (not p["raw_present"] and (
                _content_is(path, p["target_primary"]) if disp == "duplicate"
                else (isfile(path) and p.get("sha256") and sha256(path) == p["sha256"])))
            if tree_identity(path, p["target_primary"]) == "same":
                L["action"], L["why"] = "done", f"already the survivor {p['target']}"
            elif (p["raw_present"] and tree_identity(path, p["primary"]) == "same") or gone_but_still_here:
                other = _survivor_link_in(run, pdir, p)
                if other:
                    L["action"], L["why"] = "remove", f"{p['target']} is already linked here as {other}"
                else:
                    what = "same bytes" if disp == "duplicate" else "same image data and metadata"
                    L["action"], L["why"] = "replace", f"re-point at the survivor {p['target']} ({what})"
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


def carried_records(run, p, new_id):
    """{file: [new records not yet present]} -- the old id's manifest / pending rows, id rewritten.

    Read from the live files: commit B appends every carried record BEFORE it removes any old one, so a
    file whose old records are gone has had its carried records appended already.
    """
    out = {}
    for fn in QUEUE_FILES:
        path = os.path.join(run.reg_dir, fn)
        olds = csv_safe.remove_records(path, "acq_id", {p["acq_id"]}, dry_run=True)
        if not olds:
            continue
        present = {r.rstrip(b"\r\n") for r in csv_safe.remove_records(path, "acq_id", {new_id}, dry_run=True)}
        todo = [n for n in (reidentify.carry_record(r, p["acq_id"], new_id) for r in olds)
                if n.rstrip(b"\r\n") not in present]
        if todo:
            out[fn] = todo
    return out


def plan_rows(run, p):
    """Rows the commit will remove (or, once committed, still has to remove) -- and, for a re-identify,
    the rows it will add."""
    acq = p["acq_id"]
    rows = {}
    if acq in run.live:
        rows["registry_raw.csv"] = 1
    for fn in QUEUE_FILES:
        path = os.path.join(run.reg_dir, fn)
        n = len(csv_safe.remove_records(path, "acq_id", {acq}, dry_run=True))
        if n:
            rows[fn] = n
    p["rows"] = rows
    # Subjects are never deleted (06 §2.8.3): the retiree's subject rows stay, referenced or not.
    p["subjects_kept"] = subject_ids(p["row"])
    if p["disposition"] == "reidentified":
        add = {} if p["target"] in run.live else {"registry_raw.csv": 1}
        add.update({fn: len(r) for fn, r in carried_records(run, p, p["target"]).items()})
        p["rows_add"] = add


def has_work(p):
    return bool(p["actions"] or p["rows"] or p.get("rows_add")
                or p["state"] in ("fresh", "commit-interrupted", "orphan-candidate")
                or any(L["action"] in ("replace", "remove") for L in p["links"])
                or missing_events(p))


def missing_events(p):
    out = []
    for L in p["links"]:
        if L["action"] in ("replace", "remove", "done", "absent", "keep"):
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
    acq, tgt, disp = p["acq_id"], p["target"], p["disposition"]
    sv = provenance.software_version_string("retire_acquisition.py")
    base = {"output_path": L["output_path"], "output_name": L["output_path"].split("/")[-1],
            "date_created": p["_today"], "creator": p["_by"], "software_version": sv,
            "parameters_ref": p["_run_id"], "lab_notebook_ref": ""}
    done_state = L.get("done_as", L["action"])
    if disp == "reidentified":
        old_code, new_code = p["changes"]["instrument"]
        if done_state == "keep":
            return dict(base, file_type="hardlink", input_refs=tgt, notes=_tag(p, "reidentified-as " + tgt),
                        process_description=f"Re-identified by retire_acquisition.py: {acq} (instrument "
                                            f"{old_code}) is now {tgt} ({new_code}), the same file; this "
                                            f"link was not changed")
        if done_state == "absent":
            return dict(base, file_type="hardlink-removed", input_refs=acq, notes=_tag(p, "retired"),
                        process_description=f"{acq} was re-identified as {tgt} by retire_acquisition.py; "
                                            f"this link was already gone (removed or renamed in the "
                                            f"project) and was not touched")
        return None
    if done_state in ("replace", "done") and disp in DUPLICATE_LIKE:
        what = ("a duplicate of {t} (byte-identical)" if disp == "duplicate" else
                "a content-equivalent duplicate of {t} (the same image data and metadata in a different "
                "file container)").format(t=tgt)
        return dict(base, file_type="hardlink", input_refs=tgt, notes=_tag(p, "replaced-by " + tgt),
                    process_description=f"Re-pointed by retire_acquisition.py: {acq} was retired as "
                                        f"{what}; this link now points at {tgt}")
    if done_state == "remove":
        what = (f"retired as a {'content-equivalent ' if disp == 'equivalent' else ''}duplicate of {tgt}, "
                f"which is already linked in this project"
                if disp in DUPLICATE_LIKE
                else f"retired as a derivative of {tgt}; moved to {nas_rel(p['_nas'], p['dest'])}")
        return dict(base, file_type="hardlink-removed", input_refs=acq, notes=_tag(p, "link-removed"),
                    process_description=f"Removed by retire_acquisition.py: {acq} {what}")
    if done_state == "absent":
        return dict(base, file_type="hardlink-removed", input_refs=acq, notes=_tag(p, "retired"),
                    process_description=f"{acq} retired by retire_acquisition.py ({disp} of "
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


def _other_rows(run, acq):
    """{file: [verbatim records, no terminator]} of the acquisition's manifest / pending rows."""
    others = {}
    for fn in QUEUE_FILES:
        recs = csv_safe.remove_records(os.path.join(run.reg_dir, fn), "acq_id", {acq}, dry_run=True)
        if recs:
            others[fn] = [r.decode("utf-8", "replace").rstrip("\r\n") for r in recs]
    return others


def _tombstone_row(run, p, raw_rec, others, **over):
    row = {
        "acq_id": p["acq_id"], "retired_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "disposition": p["disposition"], "superseded_by": p["target"],
        "reason": retired.with_evidence(p["reason"], p.get("evidence")),
        "bytes_fate": "moved" if p["disposition"] in ("derivative", "reidentified") else "deleted",
        "moved_to": nas_rel(run.nas, p["dest"]) if p["disposition"] == "derivative" else "",
        "sha256": p.get("sha256", ""),
        "original_canonical_path": (p["row"].get("canonical_path") if p["row"]
                                    else nas_rel(run.nas, p["acq_dir"]) + "/"),
        "retired_by": run.args.retired_by, "run_id": run.run_id,
        "backup_dir": run.backup_dir or "",
        "registry_raw_row": raw_rec[0].decode("utf-8").rstrip("\r\n") if raw_rec else "",
        "other_rows_removed": json.dumps(others, ensure_ascii=False, sort_keys=True),
    }
    row.update(over)
    return row


def commit(run, p):
    """The commit point. Under the registry lock; every removal byte-exact, atomic and read back."""
    acq = p["acq_id"]
    raw_csv = os.path.join(run.reg_dir, "registry_raw.csv")
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
            retired.append_retired(retired.retired_path(run.reg_dir),
                                   _tombstone_row(run, p, raw_rec, _other_rows(run, acq)))
            run.log(f"  tombstone: appended ({p['disposition']} of {p['target'] or '-'})")
            fail_point("tombstone")
        n_raw = len(csv_safe.remove_records(raw_csv, "acq_id", {acq}))
        removed = {"registry_raw.csv": n_raw} if n_raw else {}
        for fn in QUEUE_FILES:
            n = len(csv_safe.remove_records(os.path.join(run.reg_dir, fn), "acq_id", {acq}))
            if n:
                removed[fn] = n
    run.log(f"  commit: removed rows {removed or '{}'}; subject rows left as they are (never deleted): "
            f"{p.get('subjects_kept') or '-'}")
    p["rows_removed"] = removed
    fail_point("commit")


def commit_a(run, p):
    """Re-identify, commit A: allocate the new id and append the tombstone that records it. The old row
    stays live (and points at its intact folder) until commit B."""
    acq = p["acq_id"]
    raw_csv = os.path.join(run.reg_dir, "registry_raw.csv")
    with locking.registry_lock(run.reg_dir):
        registry.assert_header_compatible(raw_csv)
        tombs = retired.read_retired(retired.retired_path(run.reg_dir))
        if acq in tombs:
            return
        live = read_live(run.nas)
        if acq not in live:
            raise RuntimeError(f"{acq} vanished from registry_raw.csv during the run")
        p["row"] = live[acq]
        new_id = acq_mod.allocate_acq_id(acq.split("-")[1], p["new_code"], raw_csv, run.reg_dir)
        if new_id in live or new_id in tombs:
            raise RuntimeError(f"the allocator returned {new_id}, which is already used")
        p["target"] = new_id
        p["changes"] = reidentify.changes_for(p["row"], new_id, p.get("model_arg"))
        _set_new_paths(run, p)
        if exists(p["new_dir"]):
            raise RuntimeError(f"{p['new_dir']} already exists (an unregistered folder under the allocated id)")
        fp = p.get("fingerprint") or {}
        p["evidence"] = {"method": "reidentify/1", "changes": p["changes"], "sha256": p.get("sha256", ""),
                         "fingerprint": {k: fp.get(k) for k in ("instrument", "rule", "serials",
                                                                 "stand_keys", "stand")}}
        raw_rec = csv_safe.remove_records(raw_csv, "acq_id", {acq}, dry_run=True)
        trow = _tombstone_row(run, p, raw_rec, _other_rows(run, acq),
                              moved_to=nas_rel(run.nas, p["new_primary"]))
        retired.append_retired(retired.retired_path(run.reg_dir), trow)
        p["retired_at"] = trow["retired_at"]
    run.log(f"  commit A: new id {p['target']} allocated; tombstone appended (reidentified as {p['target']})")
    fail_point("tombstone")


def build_new_folder(run, p):
    """Re-identify: the new /raw/ folder -- a hard link to the same file + the rewritten sidecars."""
    if not p["raw_present"] or p.get("partial_old"):
        return          # the new folder was built (and verified complete) by an earlier run
    sidecars = new_sidecars(p, (p.get("retired_at") or run.today)[:10])
    os.makedirs(lp(p["new_dir"]), exist_ok=True)
    if exists(p["new_primary"]):
        if not samefile(p["new_primary"], p["primary"]):
            raise RuntimeError(f"{p['new_primary']} exists and is not the same file as {p['primary']}")
    else:
        os.link(lp(p["primary"]), lp(p["new_primary"]))
    if not samefile(p["new_primary"], p["primary"]):
        raise RuntimeError(f"{p['new_primary']} is not the same file as {p['primary']} after linking")
    written = [name for name, data in sidecars.items()
               if write_verified(os.path.join(p["new_dir"], name), data)]
    p["new_sidecars"] = sidecars
    run.log(f"  built {nas_rel(run.nas, p['new_dir'])}: primary linked (same file id), "
            f"sidecars {'written: ' + ', '.join(written) if written else 'already in place'}")
    fail_point("built")


def commit_b(run, p):
    """Re-identify, commit B: append the new row and the carried-over bookkeeping rows, then remove the
    old ones (byte-exact). Every append happens before any removal, so a resume can always tell."""
    acq, new_id = p["acq_id"], p["target"]
    raw_csv = os.path.join(run.reg_dir, "registry_raw.csv")
    tomb_path = retired.retired_path(run.reg_dir)
    with locking.registry_lock(run.reg_dir):
        registry.assert_header_compatible(raw_csv)
        live = read_live(run.nas)
        tombs = retired.read_retired(tomb_path)
        t = tombs.get(acq)
        if not t or (t.get("superseded_by") or "").strip() != new_id:
            raise RuntimeError(f"{acq}: no tombstone naming {new_id}; commit A did not land")
        added = []
        if new_id not in live:
            base = live.get(acq) or retired.original_row(t, registry.REGISTRY_FIELDS)
            if not base:
                raise RuntimeError(f"{acq}: the original row cannot be read back to build {new_id}'s row")
            registry.append_row(raw_csv, reidentify.new_row(base, p["changes"]))
            added.append("registry_raw.csv")
        for fn, recs in carried_records(run, p, new_id).items():
            for rec in recs:
                csv_safe.append_record(os.path.join(run.reg_dir, fn), rec)
            added.append(f"{fn} x{len(recs)}")
        removed = {}
        n_raw = len(csv_safe.remove_records(raw_csv, "acq_id", {acq}))
        if n_raw:
            removed["registry_raw.csv"] = n_raw
        for fn in QUEUE_FILES:
            n = len(csv_safe.remove_records(os.path.join(run.reg_dir, fn), "acq_id", {acq}))
            if n:
                removed[fn] = n
        # The window check treats a registry_raw write no newer than the tombstone file as this tool's
        # own; commit B wrote registry_raw after the build, so mark the tombstone file as just written.
        os.utime(tomb_path, None)
    run.log(f"  commit B: added {added or '-'}; removed {removed or '{}'}; subject rows left as they are: "
            f"{p.get('subjects_kept') or '-'}")
    p["rows_removed"] = removed
    fail_point("commit")


def do_links(run, p):
    """Re-point / remove links. The provenance event is appended FIRST (write-ahead): a crash between
    the event and the action leaves the link in place, and the re-run completes the action against the
    event that already describes it -- so the record never says "a researcher removed it" when this
    tool did. A re-identified acquisition's links are left as they are (same file): events only."""
    for L in p["links"]:
        if L["action"] in ("replace", "remove", "keep"):
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
        elif L["action"] == "keep":
            if tree_identity(L["path"], p["new_primary"]) != "same":
                raise RuntimeError(f"{L['path']} is not the same file as {p['new_primary']}")
            L["done_as"] = "keep"
            run.log(f"  link kept: {nas_rel(run.nas, L['path'])} (same file, now {p['target']})")
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
    elif p["disposition"] == "equivalent":
        if not p["hashes_verified"]:
            diffs, _ev = equivalence(p["primary"], p["target_primary"])
            if diffs:
                raise RuntimeError(f"{acq}: no longer content-equivalent to {p['target']} -- NOT deleted")
        if p.get("sha256") and sha256(p["primary"]) != p["sha256"]:
            raise RuntimeError(f"{acq}: the primary changed since it was compared -- NOT deleted")
    elif p["disposition"] == "derivative":
        if tree_identity(p["dest"], p["primary"]) != "same" or \
                tree_digest(tree_hashes(p["dest"])) != p["sha256"]:
            raise RuntimeError(f"{acq}: {p['dest']} does not verify -- /raw/ NOT deleted")
    elif p["disposition"] == "reidentified":
        remove_old_folder(run, p)
        fail_point("bytes")
        return
    remove_tree_or_file(p["acq_dir"])
    if exists(p["acq_dir"]):
        raise RuntimeError(f"{p['acq_dir']} still exists after delete")
    run.log(f"  /raw/ folder deleted: {nas_rel(run.nas, p['acq_dir'])}")
    fail_point("bytes")


def new_folder_complete(p, sha):
    """True when the new folder holds the primary and three sidecars that name the new id (from disk)."""
    if not isfile(p["new_primary"]) or not all(isfile(os.path.join(p["new_dir"], s)) for s in SIDECARS):
        return False
    try:
        got = {n: read_bytes(os.path.join(p["new_dir"], n)) for n in SIDECARS}
        aid, inst, files = reidentify.sidecar_identity(got)
    except (OSError, ValueError):
        return False
    return (aid == p["target"] and inst == p["new_code"] and p["target"].encode() in got["README.txt"]
            and (files or {}).get(p["changes"]["primary_file_name"][1]) == sha)


def remove_old_folder(run, p):
    """Re-identify: remove the old folder only once the new one is complete and registered."""
    acq = p["acq_id"]
    if p["target"] not in read_live(run.nas):
        raise RuntimeError(f"{acq}: {p['target']} is not live -- old folder NOT deleted")
    if not isfile(p["new_primary"]) or (exists(p["primary"]) and not samefile(p["new_primary"], p["primary"])):
        raise RuntimeError(f"{acq}: {p['new_primary']} is not the same file as the old primary -- NOT deleted")
    if p.get("partial_old"):
        if not new_folder_complete(p, p.get("sha256")):
            raise RuntimeError(f"{acq}: the new folder is not complete -- old folder NOT deleted")
    else:
        want = p.get("new_sidecars") or new_sidecars(p, (p.get("retired_at") or run.today)[:10])
        for name, data in want.items():
            if read_bytes(os.path.join(p["new_dir"], name)) != data:
                raise RuntimeError(f"{acq}: {name} in the new folder is not as built -- old folder NOT deleted")
    if exists(p["primary"]):
        remove_link_name(p["primary"], p["new_primary"])
    remove_tree_or_file(p["acq_dir"])
    if exists(p["acq_dir"]):
        raise RuntimeError(f"{p['acq_dir']} still exists after delete")
    run.log(f"  old /raw/ folder deleted: {nas_rel(run.nas, p['acq_dir'])} (the file lives on as "
            f"{nas_rel(run.nas, p['new_primary'])})")


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
        t = tombs.get(acq)
        if not t:
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
            if done == "keep" and tree_identity(L["path"], p["new_primary"]) != "same":
                problems.append(f"{acq}: {L['path']} is not the same file as {p['target']}'s primary")
        if p["disposition"] == "derivative":
            if not exists(p["dest"]) or tree_digest(tree_hashes(p["dest"])) != tombs.get(acq, {}).get("sha256"):
                problems.append(f"{acq}: moved file missing or not the tombstoned SHA-256")
        if p["disposition"] == "reidentified" and t:
            problems += _self_check_reidentified(p, t, live)
        if missing_events(p):
            problems.append(f"{acq}: provenance events missing")
    return problems


def _self_check_reidentified(p, t, live):
    acq, new = p["acq_id"], p["target"]
    out = []
    if (t.get("superseded_by") or "").strip() != new or t.get("disposition") != "reidentified":
        out.append(f"{acq}: the tombstone does not say reidentified as {new}")
    if new not in live:
        return out + [f"{acq}: {new} is not live"]
    want = reidentify.new_row(retired.original_row(t, registry.REGISTRY_FIELDS), p["changes"])
    if {k: live[new].get(k, "") for k in registry.REGISTRY_FIELDS} != {k: want.get(k, "") for k in registry.REGISTRY_FIELDS}:
        out.append(f"{acq}: {new}'s registry row is not the old row with only its identity changed")
    if not isfile(p["new_primary"]):
        return out + [f"{acq}: {p['new_primary']} is missing"]
    try:
        got = {n: read_bytes(os.path.join(p["new_dir"], n)) for n in SIDECARS}
        aid, inst, files = reidentify.sidecar_identity(got)
        prim_name = p["changes"]["primary_file_name"][1]
        if aid != new or inst != p["new_code"] or (files or {}).get(prim_name) != t.get("sha256"):
            out.append(f"{acq}: the new sidecars do not name {new} / {p['new_code']} / the tombstoned SHA-256")
        if new.encode() not in got["README.txt"]:
            out.append(f"{acq}: README.txt does not name {new}")
    except (OSError, ValueError) as ex:
        out.append(f"{acq}: the new sidecars cannot be read: {ex}")
    return out


# ---- main ----------------------------------------------------------------------------------------

def window_check(run):
    lock = os.path.join(run.reg_dir, locking.LOCK_FILENAME)
    raw = os.path.join(run.reg_dir, "registry_raw.csv")
    msgs = []
    if os.path.exists(lock):
        msgs.append(f"{lock} exists: an ingest (or another registry writer) is running")
    age = time.time() - os.path.getmtime(raw) if os.path.exists(raw) else 1e9
    tomb = retired.retired_path(run.reg_dir)
    # The tool's own last commit is not an ingest: the tombstone is written just before registry_raw.
    ours = (os.path.exists(tomb) and os.path.exists(raw)
            and os.path.getmtime(tomb) >= os.path.getmtime(raw) - 5)
    if age < RECENT_WRITE_WINDOW_S and not ours and not run.args.allow_recent_registry_writes:
        msgs.append(f"registry_raw.csv changed {age / 60:.1f} min ago: an ingest may be mid-batch "
                    f"(never retire inside an ingest's window; --allow-recent-registry-writes overrides "
                    f"once you have confirmed none is running)")
    return msgs


def describe(run, p):
    head = f"{p['acq_id']}  [{p['state']}]  {p['disposition']}"
    if p["target"]:
        head += f" {_rel_word(p['disposition'])} {p['target']}"
    run.log(head)
    for m in p["info"]:
        run.log(f"    info: {m}")
    for m in p["warnings"]:
        run.log(f"    WARN: {m}")
    for a in p["actions"]:
        run.log(f"    will: {a}")
    if p.get("rows_add"):
        run.log(f"    will: add rows {p['rows_add']} (the new id's registry row; the manifest / pending rows "
                f"carried over with the id rewritten)")
    if p["rows"]:
        run.log(f"    will: remove rows {p['rows']} (subject rows are never removed; "
                f"left as they are: {p.get('subjects_kept') or '-'})")
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
                    "moved_to", "rows_removed", "subjects_kept", "links", "message", "evidence"])
        for p in plans:
            res, msg = results.get(p["acq_id"], ("", ""))
            moved = (nas_rel(run.nas, p["dest"]) if p.get("dest") else
                     nas_rel(run.nas, p["new_primary"]) if p.get("new_primary") else "")
            w.writerow([p["acq_id"], p["disposition"], p["target"], p["state"], res, p.get("sha256", ""),
                        moved, json.dumps(p.get("rows_removed", {})), ";".join(p.get("subjects_kept", [])),
                        "; ".join(f"{L.get('done_as', L['action'])}:{L['output_path']}@"
                                  f"{os.path.basename(L['project_dir'])}" for L in p["links"]), msg,
                        json.dumps(p.get("evidence") or {}, sort_keys=True)])
    with open(os.path.join(run.backup_dir, f"{run.run_id}.log"), "w", encoding="utf-8") as f:
        f.write(run.buf.getvalue())
    print(f"report: {path}")


def execute_one(run, p):
    if p["disposition"] == "reidentified":
        commit_a(run, p)
        build_new_folder(run, p)
        commit_b(run, p)
        do_links(run, p)
        do_bytes(run, p)
        do_provenance(run, p)
        return
    if p["disposition"] == "derivative":
        place_derivative(run, p)
        fail_point("placed")
    if p["state"] != "committed" or p["rows"]:
        commit(run, p)
    do_links(run, p)
    do_bytes(run, p)
    do_provenance(run, p)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--nas-root", required=True)
    ap.add_argument("--acq-id")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--duplicate-of", metavar="ACQ-ID", help="the surviving (live) acquisition")
    g.add_argument("--equivalent-of", metavar="ACQ-ID",
                   help="the surviving (live) acquisition of a .czi re-save (content-equivalent)")
    g.add_argument("--derivative-of", metavar="ACQ-ID", help="the original (live) acquisition")
    g.add_argument("--orphan", action="store_true", help="a /raw/ folder with no registry row")
    g.add_argument("--reidentify-as", metavar="CODE", help="re-identify under this instrument code")
    ap.add_argument("--instrument-model", help="re-identify: also set instrument_model (default: keep it)")
    ap.add_argument("--to-project", help="derivative: the project (name or PROJ-ID) to move it into")
    ap.add_argument("--subfolder", default=DEFAULT_SUBFOLDER, help="derivative: inside the project")
    ap.add_argument("--dest-name", help="derivative: file name in the subfolder (default: its original name)")
    ap.add_argument("--reason")
    ap.add_argument("--list", help="CSV: acq_id,disposition,target_acq_id,to_project,reason"
                                   "[,subfolder,dest_name,new_instrument,instrument_model]")
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
    if args.acq_id and not (args.duplicate_of or args.equivalent_of or args.derivative_of or args.orphan
                            or args.reidentify_as):
        ap.error("--acq-id needs --duplicate-of, --equivalent-of, --derivative-of, --orphan or --reidentify-as")
    if args.instrument_model and not args.reidentify_as:
        ap.error("--instrument-model goes with --reidentify-as (in a --list, use its instrument_model column)")
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
            execute_one(run, p)
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
