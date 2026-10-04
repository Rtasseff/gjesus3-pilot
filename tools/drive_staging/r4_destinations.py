#!/usr/bin/env python3
"""r4_destinations.py -- where each r4 derivative lands: stream A's shared short-path rule.

Ryan, 2026-10-04: no long paths and no zips. Every file from the historical drives that is placed on
gjesus3 now lands at

    <project>\\working\\historical_drives\\<FRIO-X6 | MFB-Disco-2>\\<study folder>\\<path below>\\<file>

inside a 240-character budget on \\\\GJESUS3\\gjesus3\\, with deterministic shortening of the fewest
folders (stream A's `tools/drive_staging/historical_paths.py`, branch feat/drives-nonraw-placement).
Stream A has already COPIED non-raw material into every target project, so each tree has a frozen
`_PATHMAP.csv` and an `_INDEX.csv` on the NAS; a derivative must land in the SAME folder A used for the
other files of its drive folder, so this module reads those trees and only CALLS A's functions: it does not
re-implement the rule.

  plan_destinations   {acq_id: destination} per project tree (Planner + the tree's frozen _PATHMAP)
  check_plan          budget, uniqueness, nothing exists yet, same folder as A's files from that drive folder
  index_rows_for      one `_INDEX.csv` row per retired derivative (the note says whose derivative it was)
  merge_index_rows    MERGE (a superset of the existing rows, never an overwrite)
  merge_pathmap_rows  the same for `_PATHMAP.csv` (new folders are frozen as decided)

Stream A's modules are imported READ-ONLY (no bytecode is written next to them). Until stream A merges
they are looked for in its worktree; set R4_STREAM_A_DIR to point elsewhere.
"""
import collections
import csv
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(HERE)

STREAM_A_DEFAULT = (r"C:\Users\rtasseff\OneDrive - CIC biomaGUNE\projects\DataInfra\gjesus3-archive"
                    r"\gjesus3-dev\drives-nonraw-placement\tools\drive_staging")
NEEDED = ("historical_paths.py", "nonraw_placement.py")

NOTE_TEXT = "retired derivative of {target}, formerly {old}"


class StreamAMissing(RuntimeError):
    pass


def stream_a_dir():
    """Where stream A's historical_paths.py and nonraw_placement.py are: beside this file once stream A has
    merged, else R4_STREAM_A_DIR, else its worktree."""
    for d in (HERE, os.environ.get("R4_STREAM_A_DIR", ""), STREAM_A_DEFAULT):
        if d and all(os.path.exists(os.path.join(d, n)) for n in NEEDED):
            return d
    raise StreamAMissing("stream A's tools/drive_staging/historical_paths.py and nonraw_placement.py not found "
                         f"(looked beside this file, in $R4_STREAM_A_DIR and in {STREAM_A_DEFAULT})")


_A = []


def load_stream_a():
    """(historical_paths, nonraw_placement) of stream A. Read-only: no .pyc is written beside them, and
    sys.path is restored (nonraw_placement puts its own folders first while it imports)."""
    if _A:
        return _A[0]
    d = stream_a_dir()
    saved_path, saved_flag = list(sys.path), sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    sys.path.insert(0, d)
    sys.path.insert(1, TOOLS)               # `ingest` (project_naming) from this worktree
    try:
        import historical_paths as H
        import nonraw_placement as NP
    finally:
        sys.path[:] = saved_path
        sys.dont_write_bytecode = saved_flag
    _A.append((H, NP))
    return _A[0]


def rcsv(path):
    with io.open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------------------------------
# the study folder (root) of a file: stream A's row_root, with a project-aware claim lookup
# ---------------------------------------------------------------------------------------------

def claim_roots_by_key(claims_csv=None):
    """{normalised claim-root segments: {projects that claim that folder}}, from claims.csv as stream A's
    load_claim_roots reads it. A's version keeps ONE project per folder (the last), so a folder claimed by
    two projects (each from a file-name token) looks root-less to the other; here each project keeps its own.
    Also fills A's FILENAME_ROOTS, which its promote_root consults."""
    H, NP = load_stream_a()
    path = claims_csv or os.path.join(NP.ANALYSIS, "codes", "claims.csv")
    out = collections.defaultdict(set)
    for c in rcsv(path):
        proj = NP.project_for(c["verdict"], c["proposed_project"], c["claim_root"])
        if not proj and c["verdict"] == "SHADOWED":
            proj = c["proposed_project"] or None
        if proj:
            key = H.claim_root_segments(c["claim_root"])
            out[key].add(proj)
            if c["source"] in ("filename", "archive-member-filename"):
                NP.FILENAME_ROOTS.add(key)
    return out


class RootsFor:
    """The dict-like `claim_roots` that stream A's row_root expects, for ONE project."""

    def __init__(self, by_key, project):
        self.by_key, self.project = by_key, project

    def get(self, key, default=None):
        return self.project if self.project in self.by_key.get(key, ()) else default


# ---------------------------------------------------------------------------------------------
# the plan
# ---------------------------------------------------------------------------------------------

class Plan:
    """dests[acq_id] = {project, base, dest (from the NAS root), subfolder, dest_name, unc_len, shortened, root};
    trees[project] = (planner, items, base)."""

    def __init__(self):
        self.dests = {}
        self.trees = {}


def split_dest(dest, project_folder):
    """(subfolder inside the project folder, file name) of a destination `projects\\<folder>\\...\\<file>`."""
    head = f"projects\\{project_folder}\\"
    if not dest.lower().startswith(head.lower()):
        raise ValueError(f"{dest!r} is not under {head!r}")
    rel = dest[len(head):]
    sub, _, name = rel.rpartition("\\")
    return sub, name


def plan_destinations(rows, members, nas, by_key=None, projects=None):
    """rows: [{acq_id, to_project}]; members: {acq_id: members.csv row}. One Planner per project tree, with the
    tree's frozen _PATHMAP.csv read from the NAS, planned over ALL the rows of that project at once (the
    shortening is a global greedy per tree). Raises historical_paths.BudgetError if a path cannot fit."""
    H, NP = load_stream_a()
    projects = projects if projects is not None else NP.load_projects(nas)
    by_key = by_key if by_key is not None else claim_roots_by_key()
    plan = Plan()
    by_proj = collections.defaultdict(list)
    for r in rows:
        by_proj[r["to_project"]].append(r)
    for proj, rs in sorted(by_proj.items()):
        folder = NP.project_folder(proj, projects)
        base = "\\".join(["projects", folder, *NP.SUBDIR])
        planner = H.Planner(base)
        planner.load_pathmap(os.path.join(nas, base, H.PATHMAP_NAME))
        items = []
        for r in sorted(rs, key=lambda x: x["acq_id"]):
            m = members[r["acq_id"]]
            row = {"decision": "place", "project_name": proj, "relpath": m["relpath"], "archive": m["archive"],
                   "member": m["member"], "reason": "", "row": r["acq_id"]}
            items.append(H.Item(id=r["acq_id"], drive=m["drive"], relpath=m["relpath"], archive=m["archive"],
                                member=m["member"], root=NP.row_root(row, RootsFor(by_key, proj)),
                                extra={"size": m["size"], "sha256": m["sha256"], "claim_id": "", "why": ""}))
        dests = planner.plan(items)
        plan.trees[proj] = (planner, items, base)
        for it in items:
            sub, name = split_dest(dests[it.id], folder)
            plan.dests[it.id] = {"project": proj, "base": base, "dest": dests[it.id], "subfolder": sub,
                                 "dest_name": name, "unc_len": H.unc_len(dests[it.id]),
                                 "shortened": bool(it.extra.get("shortened")), "root": it.root}
    return plan


def tree_index_paths(nas, base, H):
    """Lower-cased new_path -> index row of the tree's existing _INDEX.csv ({} if there is none)."""
    p = os.path.join(nas, base, H.INDEX_NAME)
    return {r["new_path"].lower(): r for r in rcsv(p)} if os.path.exists(p) else {}


def check_plan(plan, nas, members):
    """Read-only checks of a plan against the NAS. -> (report dict, problems list)."""
    H, NP = load_stream_a()
    problems, seen = [], {}
    stat = {"items": len(plan.dests), "max_unc": 0, "max_j": 0, "over_budget": 0, "shortened": 0, "no_root": 0,
            "exists": 0, "in_a_index": 0, "folder_agree": 0, "folder_differ": 0, "folder_no_a_file": 0}
    a_index, a_bydir = {}, {}
    for proj, (_planner, _items, base) in plan.trees.items():
        a_index[proj] = tree_index_paths(nas, base, H)
        bydir = collections.defaultdict(set)
        for ir in a_index[proj].values():
            od = ir["original_path"].rsplit("\\", 1)[0].lower()
            bydir[od].add(ir["new_path"].rsplit("\\", 1)[0].lower() if "\\" in ir["new_path"] else "")
        a_bydir[proj] = bydir
    for acq, d in sorted(plan.dests.items()):
        stat["max_unc"] = max(stat["max_unc"], d["unc_len"])
        stat["max_j"] = max(stat["max_j"], len(nas) + 1 + len(d["dest"]))
        stat["shortened"] += d["shortened"]
        stat["no_root"] += d["root"] is None
        if d["unc_len"] > H.BUDGET:
            stat["over_budget"] += 1
            problems.append(f"{acq}: {d['unc_len']} characters (budget {H.BUDGET})")
        if any(len(c) > H.COMPONENT_MAX for c in d["dest"].split("\\")):
            problems.append(f"{acq}: a component over {H.COMPONENT_MAX} characters")
        k = d["dest"].lower()
        if seen.setdefault(k, acq) != acq:
            problems.append(f"{acq} and {seen[k]} share the destination {d['dest']}")
        if os.path.exists(NP.lp(os.path.join(nas, d["dest"]))):
            stat["exists"] += 1
            problems.append(f"{acq}: the destination file already exists: {d['dest']}")
        new_path = d["dest"][len(d["base"]) + 1:].lower()
        if new_path in a_index[d["project"]]:
            stat["in_a_index"] += 1
            problems.append(f"{acq}: the destination is already in the tree's _INDEX.csv: {d['dest']}")
        m = members[acq]
        od = H.original_display(m["drive"], m["relpath"], m["archive"], m["member"]).rsplit("\\", 1)[0].lower()
        mine = new_path.rsplit("\\", 1)[0]
        if od in a_bydir[d["project"]]:
            if mine in a_bydir[d["project"]][od]:
                stat["folder_agree"] += 1
            else:
                stat["folder_differ"] += 1
                problems.append(f"{acq}: A put the other files of {od} in {sorted(a_bydir[d['project']][od])}, "
                                f"this goes to {mine!r}")
        else:
            stat["folder_no_a_file"] += 1
    return stat, problems


# ---------------------------------------------------------------------------------------------
# the index / pathmap / origin documents (the merge step, after the retire run)
# ---------------------------------------------------------------------------------------------

def index_rows_for(plan, members, targets, only=None):
    """{project: [_INDEX.csv rows]} for the retired derivatives in `plan` (only those in `only`, if given).
    `targets` = {acq_id: original ACQ-ID}. The note names the original and the retired id."""
    H, _NP = load_stream_a()
    out = {}
    for proj, (_planner, items, base) in plan.trees.items():
        items = [i for i in items if only is None or i.id in only]
        dests = {i.id: plan.dests[i.id]["dest"] for i in items}
        rows = H.index_rows(dests, items, base)
        by_path = {dests[i.id][len(base) + 1:]: i.id for i in items}
        for r in rows:
            acq = by_path[r["new_path"]]
            r["note"] = NOTE_TEXT.format(target=targets[acq], old=acq)
            r["claim_id"] = ""
        out[proj] = rows
    return out


def planned_nodes(plan, only=None):
    """{project: {folder node key: rendered path below the tree base}} for every folder on the way to the
    planned files (only those in `only`, if given): what `_PATHMAP.csv` must hold so these names stay frozen."""
    out = {}
    for proj, (planner, items, _base) in plan.trees.items():
        nodes = {}
        for it in items:
            if only is not None and it.id not in only:
                continue
            segs, ri = it.extra["segs"], it.extra["ri"]
            for i in range(ri if ri is not None else 0, len(segs) - 1):
                nk = planner.node_key(it.drive, segs, i)
                nodes[nk] = planner.nodes[nk]
        out[proj] = nodes
    return out


def _key_index(r):
    return r["new_path"].lower()


def merge_sorted(existing, new, key):
    """existing + new in key order WITHOUT reordering the existing rows: if `existing` is sorted by `key`
    the new rows are interleaved (stable, existing first on a tie); if it is not, the new rows are appended
    (sorted). Deterministic."""
    new = sorted(new, key=key)
    ks = [key(r) for r in existing]
    if ks != sorted(ks):
        return list(existing) + new
    out, i = [], 0
    for n in new:
        kn = key(n)
        while i < len(existing) and key(existing[i]) <= kn:
            out.append(existing[i])
            i += 1
        out.append(n)
    out.extend(existing[i:])
    return out


def merge_index_rows(existing, new):
    """-> (merged rows, n_added, n_already, conflicts). A new row whose new_path (case-insensitive) is already
    in the index is `already` when the SHA-256 is the same and its note says it is a retired derivative; a
    different file at that path is a conflict, and nothing is merged for it."""
    by = {_key_index(r): r for r in existing}
    add, already, conflicts = [], 0, []
    for r in new:
        old = by.get(_key_index(r))
        if old is None:
            add.append(r)
        elif old.get("sha256") == r.get("sha256") and "retired derivative" in (old.get("note") or ""):
            already += 1
        else:
            conflicts.append(f"{r['new_path']}: the index already has a different row (sha256 "
                             f"{(old.get('sha256') or '')[:12]} vs {(r.get('sha256') or '')[:12]})")
    return merge_sorted(existing, add, _key_index), len(add), already, conflicts


def merge_pathmap_rows(existing, planned):
    """existing: [{node_key, rendered}] from the NAS; planned: the planner's {node_key: rendered}. A folder already
    frozen keeps its name (a different rendering is a conflict); new folders are added. -> (rows, n_added, conflicts)"""
    have = {r["node_key"]: r["rendered"] for r in existing}
    add, conflicts = [], []
    for k, v in sorted(planned.items()):
        if k in have:
            if have[k] != v:
                conflicts.append(f"{k}: frozen as {have[k]!r}, planned as {v!r}")
        else:
            add.append({"node_key": k, "rendered": v})
    return merge_sorted(existing, add, lambda r: r["node_key"]), len(add), conflicts


FILLED_FIELDS = ("new_path", "drive", "archive", "original_path", "size", "sha256", "claim_id", "shortened", "note")


def read_header(path):
    """The header (column names) of a CSV."""
    with io.open(path, encoding="utf-8-sig", newline="") as f:
        return next(csv.reader(f))


def index_fields_problem(fields, H=None):
    """Why an existing _INDEX.csv header cannot take our rows (None if it can). Stream A added the `why` column
    after it had written some trees, so an older index has 9 columns: it is merged under ITS header."""
    H = H or load_stream_a()[0]
    missing = [f for f in FILLED_FIELDS if f not in fields]
    unknown = [f for f in fields if f not in H.INDEX_FIELDS]
    if missing or unknown:
        return f"header {fields}: missing {missing}, unknown {unknown}"
    return None


def serialize_index(rows, H=None, fields=None):
    """_INDEX.csv exactly as stream A's tree_documents writes it: UTF-8 with a BOM, CRLF. `fields` = the columns
    (default INDEX_FIELDS; an existing file's own header when merging into it, so its format never changes)."""
    H = H or load_stream_a()[0]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields or H.INDEX_FIELDS, extrasaction="ignore", lineterminator="\r\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue().encode("utf-8-sig")


def serialize_pathmap(rows):
    """_PATHMAP.csv as historical_paths.write_pathmap writes it (BOM, CRLF)."""
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=["node_key", "rendered"], lineterminator="\r\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue().encode("utf-8-sig")


def new_origin_docs(plan, nas, only=None):
    """{path relative to the NAS root: bytes}: an `_ORIGIN.txt` for every study folder this plan creates that has
    none yet (an existing one is never touched), and only where something was dropped above the folder: a folder
    whose path here IS its path on the drive (no study folder on the way, or the drive's own top folder) has
    nothing to say. Only the files in `only`, if given."""
    H, _NP = load_stream_a()
    docs = {}
    for _proj, (planner, items, base) in plan.trees.items():
        items = [i for i in items if only is None or i.id in only]
        for folder, origs in planner.origins(items).items():
            rest = folder.partition("\\")[2].lower()
            if all(o.partition("\\")[2].lower() == rest for o in origs):
                continue
            rel = f"{base}\\{folder}\\{H.ORIGIN_NAME}"
            if not os.path.exists(os.path.join(nas, rel)):
                docs[rel] = H.origin_text(origs).encode("utf-8")
    return docs
