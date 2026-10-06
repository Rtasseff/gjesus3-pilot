#!/usr/bin/env python3
"""repair_link_collisions.py -- audit every project's raw_linked\\ by file identity, and give each
acquisition the old silent merge left without a link its own link. Additive only.

    python tools/repair_link_collisions.py audit  --nas-root "J:\\gjesus3-data" --out <dir>
    python tools/repair_link_collisions.py repair --nas-root "J:\\gjesus3-data" --out <dir>            (dry run)
    python tools/repair_link_collisions.py repair --nas-root "J:\\gjesus3-data" --out <dir> --execute  (writes)
    python tools/repair_link_collisions.py prune-foreign --nas-root "J:\\gjesus3-data" --out <dir> [--execute]

WHY. Until 2026-10-05 `linker.create_hardlink` merged a second acquisition into a link name that
was already taken: a folder primary was linked file by file into the first acquisition's folder,
and a file primary was skipped, both silently. Stream F (2026-10-04) measured 209 production
acquisitions without a link of their own on 44 multi-study MRI animal-days. The linker now refuses
a taken name; this tool finds and repairs what the old behaviour left behind. Ryan approved the
repair on 2026-10-05: "the missing link folders are added under distinct names. Additive only;
nothing is removed."

AUDIT (read-only). Every live registry row with a project, against that project's raw_linked\\,
by FILE ID (the hard links share the raw file's id), never by name alone. Each acquisition is:
  OK                 a link holds exactly its files
  OK-EXTRA           a link holds all its files plus files of no live acquisition (a researcher's)
  POLLUTED           a link holds all its files plus ANOTHER acquisition's files (the merge target)
  MISSING            no link of its own, and a same-name partner exists: some of its files sit in a
                     folder with another acquisition's files, or its planned link name is held by
                     another acquisition (all of its file names clashed, so none were added)
  PARTIAL-OWN        a link holds only some of its files and nothing of anyone else's (an empty
                     shell, an interrupted run, or files a researcher deleted)
  RESEARCHER-PRUNED  no link, none of its files anywhere in raw_linked\\, and no partner: allowed
                     (05_PROJECTS §3a) and never "repaired"
  PENDING-LINK       no link, and queued in registries/pending_links.csv
  plus CLOSED-PROJECT / NO-FOLDER / NO-RAW / EMPTY-PRIMARY, which are not audited.
Writes <out>\\link_audit.csv (one row per acquisition and project), <out>\\link_polluted.csv (one row
per link entry holding more than one acquisition's files -- the list for Ryan; nothing is removed
here) and <out>\\link_audit_summary.txt.

REPAIR (dry run unless --execute). For each MISSING acquisition: its own link under the CURRENT
convention's name (the internal-MRI template since 2026-10-05:
MRI_<sample>_<date>_<study HHMM>_<exam>_<recons>, the study time from its own study folder name).
The name must be free, checked before any write, and unique within the plan; a name that is not
is reported and skipped. --execute first backs up every touched project's provenance.csv and
index.html to a fresh dated folder off the NAS (SHA-256 verified), then per acquisition: the link
(linker.create_hardlink, which refuses a taken name), a check that the link is exactly its files,
and a provenance row; then regenerates each touched project's index.html. Nothing is removed or
replaced. A re-run is a no-op (a repaired acquisition audits as OK). Only MRI acquisitions have a
new convention; any other MISSING acquisition is reported for a decision, not linked -- unless
`--include-file-primaries`, which gives a FILE-primary victim (microscopy `.czi`) the rule the
historical-drives ingest already uses in raw_linked\\: `<INSTR>_<stem>_<YYYYMMDD><ext>`, else
`<INSTR>_<stem>_<ACQ-ID><ext>`. Use it only with an explicit decision.

PRUNE-FOREIGN (dry run unless --execute; Ryan, 2026-10-05: "remove the foreign links from the
POLLUTED folders, foreign names only"). For each POLLUTED folder, the directory entries whose file
belongs to ANOTHER acquisition are removed, and nothing else: never a file of the folder's own
acquisition, never a file of no live acquisition, never the last name of anything. Each name is
removed only if the very same file (os.path.samefile) is also reachable from its own acquisition's
raw primary AND from that acquisition's own complete link (run `repair` first). --execute backs up
each touched project's provenance.csv and index.html plus a manifest of every name it will remove
(SHA-256 verified), appends one provenance event per folder BEFORE touching it (write-ahead;
file_type `hardlink-removed`, as the retire tool does), re-checks every precondition just before
each removal, verifies each folder is then exactly its own acquisition's files
(linker.inspect_link_target -> own), and regenerates the touched projects' index.html. A re-run
finds nothing to remove.
"""
import argparse
import contextlib
import csv
import datetime as dt
import hashlib
import io
import json
import os
import re
import shutil
import struct
import subprocess
import sys
from collections import Counter, defaultdict

TOOLS = os.path.dirname(os.path.abspath(__file__))
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

import yaml  # noqa: E402

from ingest import filename_parser, linker, provenance, resolver  # noqa: E402
from ingest import project_ids as pids  # noqa: E402

MRI_TEMPLATE = os.path.join(TOOLS, "templates", "instruments", "mri_bruker.yaml")
# The internal-MRI link name before 2026-10-05: what every existing MRI link was planned with.
OLD_MRI_LINK = "MRI_${sample_id}_${acq_date}_${discovered.mri_exam_number}_${discovered.mri_recon_indices}"
BACKUP_ROOT = r"C:\Users\rtasseff\temp"

AUDIT_FIELDS = ["project_id", "project_name", "acq_id", "instrument", "class", "reason", "n_files",
                "own_link", "partners", "planned_name", "original_name", "ingest_config"]
POLLUTED_FIELDS = ["project_id", "project_name", "link", "kind", "n_files", "complete_for",
                   "owners", "unknown_files", "missing_victims"]
PLAN_FIELDS = ["project_id", "project_name", "acq_id", "action", "new_link", "reason", "partners",
               "raw_primary", "n_files"]
PRUNE_FIELDS = ["project_id", "project_name", "folder", "owner", "name", "file_id", "file_owner",
                "file_owner_link", "action", "reason"]


# ------------------------------------------------------------------------------------ file ids

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _CreateFileW = _k32.CreateFileW
    _CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                             wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    _CreateFileW.restype = wintypes.HANDLE
    _GetInfoEx = _k32.GetFileInformationByHandleEx
    _GetInfoEx.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
    _GetInfoEx.restype = wintypes.BOOL
    _CloseHandle = _k32.CloseHandle
    _INVALID = wintypes.HANDLE(-1).value

    def _list_ids_win(path):
        """{name: (file id, is_dir)} for one directory in ONE handle: FileIdBothDirectoryInfo.

        Over SMB that is one directory query per ~64 KB of entries instead of one open + stat per
        file (measured 2026-10-05 on J:: 0.11 ms vs 2.56 ms per file, and the same id as
        os.stat().st_ino for 1,333 of 1,333 files)."""
        p = path if path.startswith("\\\\") else "\\\\?\\" + os.path.abspath(path)
        h = _CreateFileW(p, 0x0001, 7, None, 3, 0x02000000, None)   # LIST_DIRECTORY, share all, BACKUP_SEMANTICS
        if h in (None, _INVALID):
            raise OSError(ctypes.get_last_error(), "cannot open directory", path)
        out = {}
        buf = ctypes.create_string_buffer(64 * 1024)
        cls = 11   # FileIdBothDirectoryRestartInfo, then FileIdBothDirectoryInfo
        try:
            while True:
                if not _GetInfoEx(h, cls, buf, len(buf)):
                    err = ctypes.get_last_error()
                    if err == 18:   # ERROR_NO_MORE_FILES
                        break
                    raise OSError(err, "directory query failed", path)
                cls = 10
                raw, off = buf.raw, 0
                while True:
                    nxt, = struct.unpack_from("<I", raw, off)
                    attrs, nlen = struct.unpack_from("<II", raw, off + 56)
                    fid, = struct.unpack_from("<Q", raw, off + 96)
                    name = raw[off + 104: off + 104 + nlen].decode("utf-16-le")
                    if name not in (".", ".."):
                        out[name] = (fid, bool(attrs & 0x10))
                    if not nxt:
                        break
                    off += nxt
        finally:
            _CloseHandle(h)
        return out


def _list_ids_portable(path):
    out = {}
    with os.scandir(path) as it:
        for e in it:
            is_dir = e.is_dir(follow_symlinks=False)
            out[e.name] = (os.stat(e.path, follow_symlinks=False).st_ino, is_dir)
    return out


def list_ids(path):
    """{name: (file id, is_dir)} of one directory's entries."""
    if sys.platform == "win32":
        try:
            return _list_ids_win(path)
        except OSError:
            pass
    return _list_ids_portable(path)


def tree_ids(path):
    """{relative path (normcased): file id} of every file under a folder."""
    out = {}
    stack = [("", path)]
    while stack:
        rel, d = stack.pop()
        for name, (fid, is_dir) in list_ids(d).items():
            r = os.path.join(rel, name) if rel else name
            if is_dir:
                stack.append((r, os.path.join(d, name)))
            else:
                out[os.path.normcase(r)] = fid
    return out


# ----------------------------------------------------------------------------------- registries

def read_csv(path):
    if not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, fields, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def raw_primary_path(nas, row):
    """The acquisition's primary (file, or <ACQ-ID>.data folder): ingest Step 12's dispatch."""
    acq = row["acq_id"]
    acq_dir = os.path.normpath(os.path.join(nas, (row.get("canonical_path") or "").strip("/")))
    primary = (row.get("primary_file_name") or "").strip()
    kind = (row.get("primary_kind") or "").strip()
    if primary and kind == "folder" and primary != acq:
        return os.path.join(acq_dir, primary)
    if primary and kind == "folder":
        return acq_dir
    if primary and not primary.endswith("/"):
        return os.path.join(acq_dir, primary)
    return acq_dir


def primary_ids(nas, row):
    """(primary path, {relpath: file id}) -- a file primary is {"": id}; None when it is missing."""
    prim = raw_primary_path(nas, row)
    if os.path.isdir(prim):
        return prim, tree_ids(prim)
    parent, name = os.path.split(prim)
    if os.path.isdir(parent):
        ent = {k.lower(): v for k, v in list_ids(parent).items()}.get(name.lower())
        if ent and not ent[1]:
            return prim, {"": ent[0]}
    return prim, None


def sidecar_discovered(nas, row):
    p = os.path.join(nas, (row.get("canonical_path") or "").strip("/").replace("/", os.sep), "metadata.json")
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f).get("discovered") or {}
    except (OSError, ValueError):
        return {}


_TEMPLATE_CACHE = {}


def config_link_template(ingest_config):
    """The `link_filename:` of the config that produced a row ("" if none / unreadable)."""
    if ingest_config not in _TEMPLATE_CACHE:
        t = ""
        if ingest_config:
            p = ingest_config if os.path.isabs(ingest_config) else os.path.join(
                os.path.dirname(TOOLS), ingest_config.replace("/", os.sep))
            try:
                with open(p, encoding="utf-8", errors="replace") as f:
                    t = (yaml.safe_load(f) or {}).get("link_filename") or ""
            except (OSError, yaml.YAMLError):
                t = ""
        _TEMPLATE_CACHE[ingest_config] = t
    return _TEMPLATE_CACHE[ingest_config]


def _resolve(template, cfg, acq):
    with contextlib.redirect_stdout(io.StringIO()):
        name = resolver.resolve_link_filename(template, cfg, acq, acq.split("-")[1])
    return (name or "").rstrip("/\\")


def planned_old_name(nas, row):
    """The link name the row's own ingest planned (what its ingest-time template resolves to)."""
    tmpl = config_link_template(row.get("ingest_config", ""))
    if row.get("instrument") == "MRI" and "study_time" in tmpl:
        tmpl = OLD_MRI_LINK   # every existing MRI row predates the 2026-10-05 template change
    cfg = dict(row)
    cfg["discovered"] = sidecar_discovered(nas, row)
    name = _resolve(tmpl, cfg, row["acq_id"]) if tmpl else ""
    if not name or "${" in name:
        name = (row.get("original_name") or "").replace("\\", "/").rstrip("/").split("/")[-1]
    return name


def _mri_template():
    with open(MRI_TEMPLATE, encoding="utf-8") as f:
        t = yaml.safe_load(f)
    return t["link_filename"], t["auto_discover"]["filename_parse"]["regex"]


def file_primary_names(row):
    """Candidate names for a FILE-primary acquisition whose link name was taken: the rule the
    historical-drives ingest already uses for raw_linked\\ (ingest_plan.py "link names: unique per
    project", nonraw_placement.link_names_for; and relink_axioscan_collisions' dated names):
    `<INSTR>_<stem>_<YYYYMMDD><ext>`, then `<INSTR>_<stem>_<ACQ-ID><ext>` (always unique)."""
    base = (row.get("original_name") or "").replace("\\", "/").rstrip("/").split("/")[-1] or row["acq_id"]
    stem, ext = os.path.splitext(base)
    inst = row.get("instrument") or "RAW"
    day = (row.get("acquisition_datetime") or "")[:10].replace("-", "") or row["acq_id"].split("-")[1]
    return [f"{inst}_{stem}_{day}{ext}", f"{inst}_{stem}_{row['acq_id']}{ext}"]


def new_convention_name(nas, row):
    """(name, why): the current internal-MRI convention's link name for an existing row, or
    (None, reason). The study time comes from the row's own study folder (its original_name)."""
    if row.get("instrument") != "MRI":
        return None, ("no new link-name convention for this instrument (MRI only) -- needs a decision; "
                      "proposed with --include-file-primaries: <INSTR>_<stem>_<YYYYMMDD><ext>")
    template, rx = _mri_template()
    on = (row.get("original_name") or "").replace("\\", "/").strip("/")
    if "/" not in on:
        return None, "original_name has no study folder to take the study time from"
    study = on.split("/")[-2]
    disc = dict(sidecar_discovered(nas, row))
    try:
        parsed = filename_parser.parse_regex(study, rx)
    except (filename_parser.FilenameParseError, ValueError):
        parsed = {}
    m = re.match(r"^\d{8}_(\d{4})\d{2}_", study)
    disc["study_time"] = parsed.get("study_time") or (m.group(1) if m else "")
    if not disc["study_time"]:
        return None, f"study folder {study!r} carries no YYYYMMDD_HHMMSS_ start time"
    cfg = dict(row)
    cfg["discovered"] = disc
    name = _resolve(template, cfg, row["acq_id"])
    if not name or "${" in name or "/" in name or "\\" in name:
        return None, f"the template does not resolve cleanly for this row ({name!r})"
    return name, "current MRI convention"


# --------------------------------------------------------------------------------------- audit

def audit(nas, only=None, log=print):
    """Return (results, polluted, per_project) -- see the module docstring. Read-only."""
    reg = os.path.join(nas, "registries")
    live = read_csv(os.path.join(reg, "registry_raw.csv"))
    projects = read_csv(os.path.join(reg, "registry_projects.csv"))
    pending = {(r.get("acq_id"), r.get("project_id")) for r in read_csv(os.path.join(reg, "pending_links.csv"))
               if (r.get("status") or "").strip() != "linked"}
    wanted = {o.lower() for o in (only or [])}
    by_proj = defaultdict(list)
    for r in live:
        for pid in pids.split_project_ids(r.get("project_id")):
            by_proj[pid].append(r)

    # File ids of every live acquisition's raw primary: the owner map. Global, so a file that belongs
    # to an acquisition of ANOTHER project still counts as "another acquisition's" in a link folder.
    log(f"reading raw file ids of {len(live)} live acquisitions ...")
    acq_ids, acq_prim, owner = {}, {}, {}
    for i, r in enumerate(live, 1):
        try:
            prim, ids = primary_ids(nas, r)
        except OSError as e:
            prim, ids = raw_primary_path(nas, r), None
            log(f"  WARN {r['acq_id']}: raw primary unreadable: {e}")
        acq_prim[r["acq_id"]] = prim
        acq_ids[r["acq_id"]] = ids
        for fid in (ids or {}).values():
            owner.setdefault(fid, r["acq_id"])
        if i % 2000 == 0:
            log(f"  ... {i}")

    results, polluted, per_project = [], [], {}
    for p in projects:
        pid, pname = p["project_id"], p.get("name") or ""
        if wanted and pid.lower() not in wanted and pname.lower() not in wanted:
            continue
        rows = by_proj.get(pid, [])
        if not rows:
            continue
        folder = os.path.join(nas, (p.get("folder_location") or "").strip("/").replace("/", os.sep))
        raw_linked = os.path.join(folder, "raw_linked")
        base = {"project_id": pid, "project_name": pname}

        def out(r, cls, reason="", **kw):
            d = dict(base, acq_id=r["acq_id"], instrument=r.get("instrument", ""), **{"class": cls},
                     reason=reason, original_name=r.get("original_name", ""),
                     ingest_config=r.get("ingest_config", ""),
                     n_files=len(acq_ids.get(r["acq_id"]) or {}))
            d.update(kw)
            results.append(d)

        if (p.get("status") or "").strip().lower() == "closed":
            for r in rows:
                out(r, "CLOSED-PROJECT", "the project is closed: its links were removed by the close-out")
            continue
        if not os.path.isdir(raw_linked):
            for r in rows:
                out(r, "NO-FOLDER", f"{raw_linked} does not exist")
            continue
        log(f"{pid} {pname}: {len(rows)} acquisitions")

        # every link entry: its name, kind, and the ids of its files
        entries = {}
        for name, (fid, is_dir) in list_ids(raw_linked).items():
            if is_dir:
                try:
                    ids = set(tree_ids(os.path.join(raw_linked, name)).values())
                except OSError as e:
                    log(f"  WARN {name}: unreadable: {e}")
                    ids = set()
                entries[name] = {"kind": "folder", "ids": ids}
            else:
                entries[name] = {"kind": "file", "ids": {fid}}
        by_lower = {n.lower(): n for n in entries}
        # Who each link name was created for (provenance: the first creator's row survives, since
        # appends are idempotent on output_path). Tells a pruned link apart from a merge victim
        # when none of an acquisition's files are left anywhere. Keyed by the EXACT name: the
        # idempotence check is case-sensitive while the share is not, so an acquisition skipped
        # under a case-variant name (`LSM9_lipofectamine_1.czi` vs `LSM9_Lipofectamine_1.czi`)
        # still got a row of its own -- a record of a link that was never made.
        created_for = defaultdict(set)
        names_for = defaultdict(set)    # acq -> every link name provenance says was created for it
        for pr in read_csv(os.path.join(folder, "provenance.csv")):
            outp = (pr.get("output_path") or "").replace("\\", "/").strip()
            if not outp.lower().startswith("raw_linked/"):
                continue
            if (pr.get("file_type") or "") not in ("hardlink", "hardlink-folder"):
                continue   # e.g. a `hardlink-removed` event (retire, prune-foreign) records no creation
            acqs = re.findall(r"ACQ-\d{8}-[A-Z0-9]+-\d{3}", pr.get("input_refs") or "")
            created_for[outp[len("raw_linked/"):]].update(acqs)
            for a in acqs:
                names_for[a].add(outp[len("raw_linked/"):])
        in_entries = defaultdict(set)   # acq -> entry names holding any of its files
        for name, e in entries.items():
            e["owners"] = Counter(owner.get(fid) for fid in e["ids"])
            for a in e["owners"]:
                if a:
                    in_entries[a].add(name)

        def others(name, me):
            return sorted(a for a in entries[name]["owners"] if a and a != me)

        missing_by_entry = defaultdict(list)
        for r in rows:
            acq = r["acq_id"]
            ids = acq_ids.get(acq)
            if ids is None:
                out(r, "NO-RAW", f"raw primary not found: {acq_prim.get(acq)}")
                continue
            mine = set(ids.values())
            if not mine:
                # Nothing to compare by file id, and nothing a link could carry. Still say whether its
                # planned name is held by another acquisition (a collision with nothing to repair).
                planned = planned_old_name(nas, r)
                hit = by_lower.get(planned.lower())
                o = []
                if hit is not None:
                    o = others(hit, acq) or sorted(created_for.get(hit, set()) - {acq})
                out(r, "EMPTY-PRIMARY", "the raw primary holds no files" + (
                    f"; its planned link name {hit} is held by another acquisition" if o else ""),
                    partners=";".join(o), planned_name=planned)
                continue
            exact, complete, partial = [], [], []
            for name in sorted(in_entries.get(acq, ())):
                eids = entries[name]["ids"]
                if eids == mine:
                    exact.append(name)
                elif mine <= eids:
                    complete.append(name)
                else:
                    partial.append(name)
            if exact:
                out(r, "OK", own_link=";".join(exact))
                continue
            foreign = [(n, others(n, acq)) for n in complete]
            if any(o for _n, o in foreign):
                n, o = next((n, o) for n, o in foreign if o)
                out(r, "POLLUTED", "its link also holds another acquisition's files",
                    own_link=n, partners=";".join(o))
                continue
            if complete:
                out(r, "OK-EXTRA", "its link also holds files of no live acquisition", own_link=complete[0])
                continue
            mixed = [(n, others(n, acq)) for n in partial if others(n, acq)]
            if mixed:
                n, o = mixed[0]
                out(r, "MISSING", f"{len(mine & entries[n]['ids'])} of its {len(mine)} files sit in "
                                  f"{n}, a link of another acquisition (the silent merge)",
                    partners=";".join(o), planned_name=n)
                missing_by_entry[n].append(acq)
                continue
            if partial:
                out(r, "PARTIAL-OWN", "a link holds only some of its files and nothing of another "
                                      "acquisition's", own_link=partial[0])
                continue
            # None of its files anywhere: a merge where every file name clashed, or a pruned link.
            # A link provenance says was created for it, under a name that no longer exists in any
            # case, was removed after it was made (e.g. a repaired link a researcher later deleted):
            # pruned, never re-made. (A name that still exists in another case is the false row a
            # case-variant victim got, so it does not count.)
            gone = sorted(n for n in names_for.get(acq, ()) if by_lower.get(n.lower()) is None)
            if gone:
                out(r, "RESEARCHER-PRUNED", f"a link created for it ({gone[0]}, provenance) has since "
                                            f"been removed", planned_name=planned_old_name(nas, r))
                continue
            planned = planned_old_name(nas, r)
            hit = by_lower.get(planned.lower())
            if hit is not None:
                e = entries[hit]
                if not e["ids"]:
                    out(r, "PARTIAL-OWN", "its planned link name is an empty folder (a shell)",
                        own_link=hit, planned_name=planned)
                    continue
                if acq in created_for.get(hit, ()):
                    out(r, "RESEARCHER-PRUNED", f"its own link {hit} was created for it (provenance) "
                                                f"and its files have since left it", planned_name=planned)
                    continue
                o = others(hit, acq)
                out(r, "MISSING", ("its planned link name is held by another acquisition, so none of "
                                   "its files were added" if o else
                                   "its planned link name is held by files of no live acquisition"),
                    partners=";".join(o), planned_name=planned)
                missing_by_entry[hit].append(acq)
                continue
            if (acq, pid) in pending:
                out(r, "PENDING-LINK", "queued in registries/pending_links.csv", planned_name=planned)
                continue
            out(r, "RESEARCHER-PRUNED", "no link, none of its files in raw_linked, no partner "
                                        "(allowed: 05_PROJECTS §3a)", planned_name=planned)

        for name, e in sorted(entries.items()):
            known = [a for a in e["owners"] if a]
            if len(known) < 2:
                continue
            complete_for = sorted(a for a in known if acq_ids.get(a) and
                                  set(acq_ids[a].values()) <= e["ids"])
            polluted.append(dict(base, link=name, kind=e["kind"], n_files=len(e["ids"]),
                                 complete_for=";".join(complete_for),
                                 owners=";".join(f"{a}:{e['owners'][a]}" for a in sorted(known)),
                                 unknown_files=e["owners"].get(None, 0),
                                 missing_victims=";".join(sorted(missing_by_entry.get(name, [])))))
    names = {p["project_id"]: p.get("name") or "" for p in projects}
    for d in results:
        per_project.setdefault(d["project_id"], (names.get(d["project_id"], ""), Counter()))[1][d["class"]] += 1
    return results, polluted, per_project


def write_audit(out_dir, results, polluted, per_project):
    os.makedirs(out_dir, exist_ok=True)
    write_csv(os.path.join(out_dir, "link_audit.csv"), AUDIT_FIELDS, results)
    write_csv(os.path.join(out_dir, "link_polluted.csv"), POLLUTED_FIELDS, polluted)
    classes = ["OK", "OK-EXTRA", "POLLUTED", "MISSING", "PARTIAL-OWN", "RESEARCHER-PRUNED",
               "PENDING-LINK", "EMPTY-PRIMARY", "NO-RAW", "CLOSED-PROJECT", "NO-FOLDER"]
    lines = ["%-10s %-24s " % ("project", "name") + " ".join("%9s" % c[:9] for c in classes)]
    total = Counter()
    for pid, (pname, c) in sorted(per_project.items()):
        total.update(c)
        lines.append("%-10s %-24s " % (pid, pname[:24]) + " ".join("%9d" % c.get(k, 0) for k in classes))
    lines.append("%-10s %-24s " % ("TOTAL", "") + " ".join("%9d" % total.get(k, 0) for k in classes))
    lines.append("")
    lines.append(f"link entries holding more than one acquisition's files: {len(polluted)}")
    text = "\n".join(lines)
    with open(os.path.join(out_dir, "link_audit_summary.txt"), "w", encoding="utf-8") as f:
        f.write(text + "\n")
    return text, total


# -------------------------------------------------------------------------------------- repair

def plan_repair(nas, results, include_file_primaries=False):
    """One plan row per MISSING acquisition: create / complete / done / blocked. Read-only.

    MRI: the current MRI convention's name. Any other instrument is blocked (no approved
    convention) unless `include_file_primaries`, when a FILE primary gets the first free name of
    `file_primary_names` -- the option the coordinator / Ryan decide on."""
    live = {r["acq_id"]: r for r in read_csv(os.path.join(nas, "registries", "registry_raw.csv"))}
    projects = {p["project_id"]: p for p in read_csv(os.path.join(nas, "registries", "registry_projects.csv"))}
    plan, claimed = [], {}
    for a in results:
        if a["class"] != "MISSING":
            continue
        row = live.get(a["acq_id"])
        p = projects.get(a["project_id"])
        base = {"project_id": a["project_id"], "project_name": a["project_name"], "acq_id": a["acq_id"],
                "partners": a.get("partners", ""), "n_files": a.get("n_files", "")}
        if not row or not p:
            plan.append(dict(base, action="blocked", reason="row or project vanished since the audit"))
            continue
        folder = os.path.join(nas, p["folder_location"].strip("/").replace("/", os.sep))
        prim = raw_primary_path(nas, row)
        if row.get("instrument") != "MRI" and include_file_primaries and os.path.isfile(prim):
            candidates, why = file_primary_names(row), "file-primary rule"
        else:
            name, why = new_convention_name(nas, row)
            candidates = [name] if name else []
        if not candidates:
            plan.append(dict(base, action="blocked", reason=why, raw_primary=prim))
            continue
        chosen = None
        for name in candidates:
            key = (a["project_id"], name.lower())
            if key in claimed:
                last = f"the same new name is planned for {claimed[key]}"
                continue
            state, _dest, detail = linker.inspect_link_target(folder, name, prim)
            if state == linker.LINK_TAKEN:
                last = f"{name} is taken: {detail}"
                continue
            chosen = (name, state, detail)
            claimed[key] = a["acq_id"]
            break
        if not chosen:
            plan.append(dict(base, action="blocked", new_link=candidates[-1], raw_primary=prim, reason=last))
            continue
        name, state, detail = chosen
        action = {"free": "create", "own": "done", "partial": "complete"}[state]
        plan.append(dict(base, action=action, new_link=name, raw_primary=prim,
                         reason=(f"{why}; name free" if state == "free" else detail)))
    return plan


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def execute_repair(nas, plan, by, backup_root=BACKUP_ROOT, log=print, regenerate_index=True):
    """Write the plan's create / complete rows. Backup first; additive only. Returns (made, errors)."""
    projects = {p["project_id"]: p for p in read_csv(os.path.join(nas, "registries", "registry_projects.csv"))}
    todo = [x for x in plan if x["action"] in ("create", "complete")]
    if not todo:
        log("nothing to write")
        return 0, 0
    touched = sorted({x["project_id"] for x in todo})
    bk = os.path.join(backup_root, f"gjesus3_link_repair_backup_{dt.datetime.now():%Y%m%d_%H%M%S}")
    if os.path.exists(bk):
        raise SystemExit(f"STOP: backup dir {bk} exists")
    os.makedirs(bk)
    for pid in touched:
        folder = os.path.join(nas, projects[pid]["folder_location"].strip("/").replace("/", os.sep))
        for fn in ("provenance.csv", "index.html"):
            src = os.path.join(folder, fn)
            if os.path.isfile(src):
                dst = os.path.join(bk, f"{pid}_{fn}")
                shutil.copy2(src, dst)
                if _sha256(src) != _sha256(dst):
                    raise SystemExit(f"STOP: backup of {src} does not verify")
    log(f"backup: {bk} ({len(touched)} projects, verified)")
    today = dt.date.today().isoformat()
    made = errors = 0
    for x in todo:
        folder = os.path.join(nas, projects[x["project_id"]]["folder_location"].strip("/").replace("/", os.sep))
        try:
            dest = linker.create_hardlink(folder, x["new_link"], x["raw_primary"])
            state, _d, detail = linker.inspect_link_target(folder, x["new_link"], x["raw_primary"])
            if state != linker.LINK_OWN:
                raise RuntimeError(f"after linking, {dest} is {state}: {detail}")
            is_dir = os.path.isdir(dest)
            provenance.append_entry(os.path.join(folder, "provenance.csv"), {
                "output_path": f"raw_linked/{x['new_link']}",
                "output_name": x["new_link"],
                "file_type": "hardlink-folder" if is_dir else "hardlink",
                "date_created": today,
                "creator": by,
                "input_refs": x["acq_id"],
                "process_description": (
                    "Link-collision repair (repair_link_collisions.py): this acquisition's own link. "
                    "Its link name had been taken by another acquisition and the old linker merged or "
                    "skipped it silently (fixed 2026-10-05)"),
                "software_version": provenance.software_version_string("repair_link_collisions.py"),
                "parameters_ref": "",
                "lab_notebook_ref": "",
                "notes": f"name taken by {x.get('partners') or 'another link'}; additive repair, "
                         f"nothing removed",
            })
            made += 1
            log(f"  LINKED {x['acq_id']} -> {x['project_name']}/raw_linked/{x['new_link']}")
        except Exception as e:  # noqa: BLE001 -- counted and reported; the rest continue
            errors += 1
            log(f"  ERROR {x['acq_id']}: {type(e).__name__}: {e}")
    if regenerate_index:
        for pid in touched:
            cmd = [sys.executable, os.path.join(TOOLS, "generate_index.py"), "--nas-root", nas, "--project", pid]
            rc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
            log(f"  index {pid}: rc={rc.returncode}")
            if rc.returncode:
                errors += 1
    return made, errors


# ------------------------------------------------------------------------------- prune-foreign

def tree_names(path):
    """[(relative path as on disk, file id)] of every file under a folder."""
    out, stack = [], [("", path)]
    while stack:
        rel, d = stack.pop()
        for name, (fid, is_dir) in list_ids(d).items():
            r = os.path.join(rel, name) if rel else name
            if is_dir:
                stack.append((r, os.path.join(d, name)))
            else:
                out.append((r, fid))
    return sorted(out)


def plan_prune(nas, results, polluted):
    """One row per file in every POLLUTED folder that is not the folder's own: `remove` when every
    precondition holds, else `keep` with the reason. Read-only; the owner's files are not listed."""
    live = {r["acq_id"]: r for r in read_csv(os.path.join(nas, "registries", "registry_raw.csv"))}
    projects = {p["project_id"]: p for p in read_csv(os.path.join(nas, "registries", "registry_projects.csv"))}
    status = {(a["project_id"], a["acq_id"]): a for a in results}
    plan = []
    for e in polluted:
        pid, folder = e["project_id"], e["link"]
        base = {"project_id": pid, "project_name": e["project_name"], "folder": folder}
        owners = [o for o in (e.get("complete_for") or "").split(";") if o]
        if len(owners) != 1 or owners[0] not in live:
            plan.append(dict(base, owner=";".join(owners), action="keep",
                             reason="not exactly one live acquisition owns this folder completely"))
            continue
        owner = owners[0]
        pdir = os.path.join(nas, projects[pid]["folder_location"].strip("/").replace("/", os.sep))
        fabs = os.path.join(pdir, "raw_linked", folder)
        own_ids = set((primary_ids(nas, live[owner])[1] or {}).values())
        cands = {}   # file id -> (acquisition, its raw relpath -> path, its own link folder or file)
        for item in (e.get("owners") or "").split(";"):
            acq = item.split(":")[0]
            if not acq or acq == owner or acq not in live:
                continue
            prim, ids = primary_ids(nas, live[acq])
            st = status.get((pid, acq), {})
            link = (st.get("own_link") or "").split(";")[0] if st.get("class") == "OK" else ""
            for rel, fid in (ids or {}).items():
                cands[fid] = (acq, os.path.join(prim, rel) if rel else prim,
                              (os.path.join(pdir, "raw_linked", link, rel) if rel else
                               os.path.join(pdir, "raw_linked", link)) if link else "", link)
        for rel, fid in tree_names(fabs):
            if fid in own_ids:
                continue
            row = dict(base, owner=owner, name=rel, file_id=fid)
            if fid not in cands:
                plan.append(dict(row, action="keep", reason="a file of no live acquisition (never removed)"))
                continue
            acq, raw_path, link_path, link = cands[fid]
            row.update(file_owner=acq, file_owner_link=link)
            here = os.path.join(fabs, rel)
            if not link:
                plan.append(dict(row, action="keep", reason=f"{acq} has no complete link of its own "
                                                            f"in this project yet (run repair first)"))
            elif not (_samefile(here, raw_path) and _samefile(here, link_path)):
                plan.append(dict(row, action="keep", reason="not the same file as its raw file and its "
                                                            "own link's copy"))
            else:
                plan.append(dict(row, action="remove", reason=f"also in /raw/ and in {acq}'s own link {link}"))
    return plan


def _samefile(a, b):
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def _remove_name(path, survivor):
    """Remove ONE name of a file that lives on under `survivor` (the retire tool's pattern): a
    read-only attribute is per FILE, shared by every name, so it is cleared only if the delete needs
    it, and then restored on the survivor."""
    import stat as _stat
    try:
        os.remove(path)
        return
    except PermissionError:
        if not getattr(os.stat(path), "st_file_attributes", 0) & 1:   # FILE_ATTRIBUTE_READONLY
            raise
    os.chmod(path, _stat.S_IWRITE)
    try:
        os.remove(path)
    finally:
        os.chmod(survivor, _stat.S_IREAD)


def execute_prune(nas, plan, by, backup_root=BACKUP_ROOT, log=print, regenerate_index=True):
    """Remove the plan's `remove` names (backup and write-ahead provenance first). Returns
    (removed, errors, verified folders, folders checked)."""
    projects = {p["project_id"]: p for p in read_csv(os.path.join(nas, "registries", "registry_projects.csv"))}
    live = {r["acq_id"]: r for r in read_csv(os.path.join(nas, "registries", "registry_raw.csv"))}
    todo = [x for x in plan if x["action"] == "remove"]
    folders = sorted({(x["project_id"], x["folder"], x["owner"]) for x in plan if x.get("owner")})
    if not todo:
        log("nothing to remove")
    touched = sorted({x["project_id"] for x in todo})
    stamp = f"{dt.datetime.now():%Y%m%d_%H%M%S}"
    if todo:
        bk = os.path.join(backup_root, f"gjesus3_link_prune_backup_{stamp}")
        if os.path.exists(bk):
            raise SystemExit(f"STOP: backup dir {bk} exists")
        os.makedirs(bk)
        for pid in touched:
            folder = os.path.join(nas, projects[pid]["folder_location"].strip("/").replace("/", os.sep))
            for fn in ("provenance.csv", "index.html"):
                src = os.path.join(folder, fn)
                if os.path.isfile(src):
                    dst = os.path.join(bk, f"{pid}_{fn}")
                    shutil.copy2(src, dst)
                    if _sha256(src) != _sha256(dst):
                        raise SystemExit(f"STOP: backup of {src} does not verify")
        manifest = os.path.join(bk, "prune_manifest.csv")
        write_csv(manifest, PRUNE_FIELDS, todo)
        log(f"backup: {bk} ({len(touched)} projects + the manifest of {len(todo)} names, verified)")
    today = dt.date.today().isoformat()
    sv = provenance.software_version_string("repair_link_collisions.py")
    removed = errors = 0
    by_folder = defaultdict(list)
    for x in todo:
        by_folder[(x["project_id"], x["folder"], x["owner"])].append(x)
    for (pid, fname, owner), items in sorted(by_folder.items()):
        pdir = os.path.join(nas, projects[pid]["folder_location"].strip("/").replace("/", os.sep))
        fabs = os.path.join(pdir, "raw_linked", fname)
        own_ids = set((primary_ids(nas, live[owner])[1] or {}).values())
        names_now = dict(tree_names(fabs))           # the folder as it is right now: relpath -> file id
        for acq in sorted({x["file_owner"] for x in items}):
            mine = [x for x in items if x["file_owner"] == acq]
            link = mine[0]["file_owner_link"]
            prim = raw_primary_path(nas, live[acq])
            rel_of = {i: r for r, i in (primary_ids(nas, live[acq])[1] or {}).items()}
            # Write-ahead: the event first, so a crash leaves a record that names what was underway.
            provenance.append_entry(os.path.join(pdir, "provenance.csv"), {
                "output_path": f"raw_linked/{fname}",
                "output_name": fname,
                "file_type": "hardlink-removed",
                "date_created": today,
                "creator": by,
                "input_refs": acq,
                "process_description": (
                    f"Link-collision cleanup (repair_link_collisions.py prune-foreign): removed {len(mine)} "
                    f"hard-link names of {acq}'s files from this folder, where the old linker had merged "
                    f"them (fixed 2026-10-05). {acq} keeps every file in /raw/ and in its own link "
                    f"raw_linked/{link}; this folder now holds only {owner}'s files"),
                "software_version": sv,
                "parameters_ref": "",
                "lab_notebook_ref": "",
                "notes": f"repair_link_collisions: {acq} foreign-names-removed",
            }, unique_on=("output_path", "notes"))
            for x in mine:
                here = os.path.join(fabs, x["name"])
                try:
                    # Every precondition again, from disk, right before this one removal.
                    fid = names_now.get(x["name"])
                    rel = rel_of.get(fid) if fid is not None else None
                    raw_path = link_path = None
                    if rel is not None:
                        raw_path = os.path.join(prim, rel) if rel else prim
                        link_path = (os.path.join(pdir, "raw_linked", link, rel) if rel
                                     else os.path.join(pdir, "raw_linked", link))
                    if (fid is None or fid in own_ids or rel is None or str(fid) != str(x["file_id"])
                            or not (_samefile(here, raw_path) and _samefile(here, link_path))):
                        raise RuntimeError("a precondition no longer holds; left as it is")
                    _remove_name(here, raw_path)
                    if os.path.lexists(here):
                        raise RuntimeError("still present after removal")
                    if not (os.path.exists(raw_path) and os.path.exists(link_path)):
                        raise RuntimeError("its raw file or own-link copy is gone")
                    removed += 1
                except Exception as e:  # noqa: BLE001 -- counted and reported; the rest continue
                    errors += 1
                    log(f"  ERROR {pid} {fname}/{x['name']}: {type(e).__name__}: {e}")
            log(f"  {pid} {fname}: removed {len(mine)} names of {acq}")
    verified = 0
    for pid, fname, owner in folders:
        if owner not in live:   # e.g. "A;B": no single owner, so nothing was removed there
            log(f"  NOT VERIFIED {pid} {fname}: no single live owner ({owner})")
            continue
        pdir = os.path.join(nas, projects[pid]["folder_location"].strip("/").replace("/", os.sep))
        state, _d, detail = linker.inspect_link_target(pdir, fname, raw_primary_path(nas, live[owner]))
        if state == linker.LINK_OWN:
            verified += 1
        else:
            log(f"  NOT VERIFIED {pid} {fname}: {state} ({detail})")
    if regenerate_index and todo:
        for pid in touched:
            cmd = [sys.executable, os.path.join(TOOLS, "generate_index.py"), "--nas-root", nas, "--project", pid]
            rc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
            log(f"  index {pid}: rc={rc.returncode}")
            if rc.returncode:
                errors += 1
    return removed, errors, verified, len(folders)


# ----------------------------------------------------------------------------------------- cli

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["audit", "repair", "prune-foreign"])
    ap.add_argument("--nas-root", required=True)
    ap.add_argument("--out", required=True, help="folder for the CSV reports (off the NAS)")
    ap.add_argument("--project", action="append", help="limit to this project (name or PROJ-id); repeatable")
    ap.add_argument("--execute", action="store_true", help="repair / prune-foreign: write (default: dry run)")
    ap.add_argument("--include-file-primaries", action="store_true",
                    help="repair: also link non-MRI FILE-primary victims under <INSTR>_<stem>_<YYYYMMDD><ext> "
                         "(else <INSTR>_<stem>_<ACQ-ID><ext>) -- only with an explicit decision")
    ap.add_argument("--by", default="Data Office", help="repair: provenance `creator`")
    args = ap.parse_args(argv)
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:
            pass
    nas = os.path.normpath(args.nas_root)
    t0 = dt.datetime.now()
    results, polluted, per_project = audit(nas, args.project)
    text, total = write_audit(args.out, results, polluted, per_project)
    print(text)
    print(f"audit took {(dt.datetime.now() - t0).seconds}s -> {args.out}")
    if args.cmd == "audit":
        return 0
    if args.cmd == "prune-foreign":
        plan = plan_prune(nas, results, polluted)
        write_csv(os.path.join(args.out, "link_prune_plan.csv"), PRUNE_FIELDS, plan)
        c = Counter(x["action"] for x in plan)
        print(f"prune plan: {dict(c)} in {len({(x['project_id'], x['folder']) for x in plan})} folders "
              f"-> {os.path.join(args.out, 'link_prune_plan.csv')}")
        for (pid, folder), n in sorted(Counter((x["project_id"], x["folder"]) for x in plan
                                               if x["action"] == "remove").items()):
            print(f"  remove {n:4d} foreign names from {pid} raw_linked/{folder}")
        for x in [x for x in plan if x["action"] != "remove"][:10]:
            print(f"  KEEP {x['project_id']} {x['folder']}/{x.get('name', '')}: {x['reason']}")
        if not args.execute:
            print("DRY RUN: nothing written. Re-run with --execute in an approved write window.")
            return 0
        removed, errors, verified, checked = execute_prune(nas, plan, args.by)
        print(f"prune: {removed} names removed, {errors} errors; {verified} of {checked} folders now "
              f"exactly their own acquisition's files")
        return 1 if errors or verified != checked else 0
    plan = plan_repair(nas, results, include_file_primaries=args.include_file_primaries)
    write_csv(os.path.join(args.out, "link_repair_plan.csv"), PLAN_FIELDS, plan)
    c = Counter(x["action"] for x in plan)
    print(f"repair plan: {dict(c)} -> {os.path.join(args.out, 'link_repair_plan.csv')}")
    for x in plan[:8]:
        print(f"  {x['action']:8s} {x['acq_id']} {x['project_name']}/raw_linked/{x.get('new_link', '')}"
              f"  ({x.get('reason', '')})")
    if not args.execute:
        print("DRY RUN: nothing written. Re-run with --execute in an approved write window.")
        return 0
    made, errors = execute_repair(nas, plan, args.by)
    print(f"repair: {made} links created, {errors} errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
