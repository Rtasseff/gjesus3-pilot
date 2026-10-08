#!/usr/bin/env python3
"""historical_paths.py -- THE destination rule for historical-drive material placed on gjesus3.

One function for every stream that puts drive material into a project folder or the holding folder
(stream A's non-raw placement, stream D's derivative retirements, stream C's LEONE-into-DTS24, the
later 2b mapping and the 2c holding folder). Ryan, 2026-10-02: no paths that throw errors, no zips
(researchers must browse); drop high-level folders and keep an index so nothing is lost.

THE RULE
  <base>\\<tag>\\<root label>\\<path below the root>\\<file>
    base   projects\\<project>\\working\\historical_drives   (or staging\\historical_drives_unassigned)
    tag    FRIO-X6 | MFB-Disco-2 | MJesus-MFB               (the drive; TAGS below)
    root   the OUTERMOST claim-root folder of the file's project on its path (a study folder such as
           `Proyecto 1019 Envejecimiento y dieta`); everything ABOVE it is dropped -- the drive's
           wrapper folders, the researcher folders, an archive's name and its repeated top folder.
           Two different roots with the same name in one tree get " (2)", " (3)" (sorted by their
           full original path). No root (the holding folder): the full original path is kept.
  Below the root:
    - an archive becomes a folder `<stem>_<ext>` (`Manon.zip` -> `Manon_zip`), and the archive's own
      top folder of the same name is not repeated;
    - BUDGET: the whole UNC path (\\\\GJESUS3\\gjesus3\\...) is <= 240 characters (19 of headroom
      under Windows' 259 for researchers' own copies and renames), and no component > 255;
    - LAST RESORT, deterministic: the fewest FOLDERS are shortened to their first 24 characters +
      "~" + 4 hex of a hash of the full name (`Comparasion expiration vs inspiraiton` ->
      `Comparasion expiration v~3f2a`); a folder is shortened for everything in it, never per file.
      A file name is shortened (stem only, extension kept) only if the folders cannot get it under
      the budget. Every destination is checked unique, case-insensitively.
  NOTHING IS LOST: per tree an `_INDEX.csv` (new path -> full original path, size, sha256, claim,
  shortened Y/N), a `README.txt`, an `_ORIGIN.txt` in each root folder naming what was dropped above
  it, and a `_PATHMAP.csv` (every folder's original -> rendered name). A later run READS the existing
  `_PATHMAP.csv`: folders already on the NAS keep their names (frozen); only new folders are decided.

    from historical_paths import Planner, Item
    p = Planner(base="projects\\\\AE-biomaGUNE-1123\\\\working\\\\historical_drives")
    p.load_pathmap(r"J:\\gjesus3-data\\projects\\AE-biomaGUNE-1123\\working\\historical_drives\\_PATHMAP.csv")
    dest = p.plan([Item(id="x", drive="D1", relpath="...", archive="", member="", root=...)])

CLI (one file, for the other streams):
    python tools/drive_staging/historical_paths.py dest --base "projects\\AE-biomaGUNE-0721\\working\\historical_drives" \\
        --drive D2 --relpath "2025-10-02 - Toshiba EXT (Backup)\\...\\x.czi" [--archive A --member M] \\
        [--root "<claim root as in claims.csv>"] [--pathmap <existing _PATHMAP.csv>]
"""
import argparse
import csv
import hashlib
import io
import os
import re
import sys
from dataclasses import dataclass, field

UNC_PREFIX = "\\\\GJESUS3\\gjesus3\\"
BUDGET = 240
COMPONENT_MAX = 255
KEEP = 24
KEEP_LEVELS = (24, 12, 6)  # graded shortening: a later run may cut NEW folders harder (old ones are frozen)
# The drives, by the code the catalogs use. D3 is M. Jesus's own working drive (WD My Passport, serial
# WX22D623YP29, volume label MJesus-MFB-biomaGUNE), staged 2026-09-29/30; its tag is the volume label
# shortened the way the first two were made (A2, tasks/drive3_projects_and_placement.md §4.1).
TAGS = {"D1": "FRIO-X6", "D2": "MFB-Disco-2", "D3": "MJesus-MFB"}
DRIVE_LABELS = {"D1": "drive1_FRIO-X6", "D2": "drive2_MFB-Disco-2", "D3": "drive3_MJesus-MFB"}
NESTED_SEP = "!"
ARCHIVE_EXT = (".zip", ".7z", ".rar")
INDEX_NAME, PATHMAP_NAME, README_NAME, ORIGIN_NAME = "_INDEX.csv", "_PATHMAP.csv", "README.txt", "_ORIGIN.txt"


# ------------------------------------------------------------------------------------------ paths

def norm(s):
    """Comparison form of a path segment: case-blind, accent-blind (the claims pass lost accents)."""
    return re.sub(r"[^\x00-\x7f]", "?", s or "").strip().lower()


def logical_segments(relpath, archive="", member=""):
    """The file's ORIGINAL location as [(name, kind)], kind in dir | archive | file. An archive member
    is the archive's relpath (its last segment an `archive`) + the member path; a nested archive
    member (`<nested>!<inner>`) adds the nested archive as another `archive` segment."""
    if not archive:
        parts = [p for p in relpath.replace("/", "\\").split("\\") if p]
        return [(p, "dir") for p in parts[:-1]] + [(parts[-1], "file")]
    a = [p for p in archive.replace("/", "\\").split("\\") if p]
    out = [(p, "dir") for p in a[:-1]] + [(a[-1], "archive")]
    chunks = member.split(NESTED_SEP)
    for i, chunk in enumerate(chunks):
        ps = [p for p in chunk.replace("\\", "/").split("/") if p]
        last = i == len(chunks) - 1
        for j, p in enumerate(ps):
            if j == len(ps) - 1:
                out.append((p, "file" if last else "archive"))
            else:
                out.append((p, "dir"))
    return out


def original_display(drive, relpath, archive="", member=""):
    """The full original path as a researcher would recognise it (for the index)."""
    label = DRIVE_LABELS.get(drive, drive)
    if not archive:
        return f"{label}\\{relpath}"
    return f"{label}\\{archive}{NESTED_SEP}{member.replace('/', chr(92))}"


def claim_root_segments(claim_root):
    """claims.csv `claim_root` (`A.zip!\\X\\Y` or `X\\Y`) -> normalised segment tuple, comparable with
    the normalised names of logical_segments()."""
    if NESTED_SEP in claim_root:
        a, m = claim_root.split(NESTED_SEP, 1)
        segs = [p for p in a.split("\\") if p] + [p for p in m.replace("/", "\\").split("\\") if p]
    else:
        segs = [p for p in claim_root.replace("/", "\\").split("\\") if p]
    return tuple(norm(s) for s in segs)


def root_index_for(segs, roots):
    """Index (in `segs`) of the OUTERMOST folder whose normalised path is in `roots` (a set of
    normalised segment tuples), or None."""
    key = []
    for i, (name, kind) in enumerate(segs[:-1]):
        key.append(norm(name))
        if tuple(key) in roots:
            return i
    return None


def archive_folder_name(name):
    stem, ext = os.path.splitext(name)
    return f"{stem}_{ext.lstrip('.')}" if ext else f"{name}_archive"


def short_name(name, keep=KEEP):
    """`<first keep chars>~<4 hex>` -- deterministic, and two different names that share a prefix
    stay apart through the hash of the FULL name."""
    h = hashlib.sha1(name.encode("utf-8")).hexdigest()[:4]
    return f"{name[:keep].rstrip(' .')}~{h}"


def short_file(name, keep=KEEP):
    stem, ext = os.path.splitext(name)
    return short_name(stem, keep) + ext


def unc_len(rel):
    return len(UNC_PREFIX) + len(rel)


# ---------------------------------------------------------------------------------------- planner

@dataclass
class Item:
    id: str
    drive: str
    relpath: str
    archive: str = ""
    member: str = ""
    root: object = None        # a normalised segment tuple (claim_root_segments), or None = keep full path
    extra: dict = field(default_factory=dict)


class BudgetError(Exception):
    pass


class Planner:
    """Destinations for one tree (one project's historical_drives, or the holding folder)."""

    def __init__(self, base, budget=BUDGET, keep=KEEP, strategy=None):
        self.base = base.strip("\\")
        self.budget = budget
        self.keep = keep
        self.strategy = strategy or os.environ.get("HP_STRATEGY", "gain")  # "gain" (default: fewest cuts measured 2026-10-02) | "longest"
        self.fixed = {}          # node key -> rendered path below base, from an existing _PATHMAP (frozen)
        self.roots = {}          # (tag, root node key) -> root label
        self.short = {}          # node key -> keep (chars kept) for folders this run renders short
        self.file_short = {}     # item id -> keep, for file names this run renders short
        self.nodes = {}          # node key -> rendered path below base (fixed + this run)
        self.pinned = {}         # full original path (lower) -> path below base, of FILES already placed

    # -- persistence --------------------------------------------------------------------------
    def load_index(self, path):
        """Pin every FILE already placed (the tree's _INDEX.csv / holding manifest.csv on the NAS): a
        re-plan returns its recorded path exactly. _PATHMAP.csv freezes folder names, but a file name
        shortened in an earlier run is only recorded here -- without this a later run could place a
        second, unshortened copy (found in the step-3 dry run, 2026-10-04: 14 files in 1019)."""
        if not path or not os.path.exists(path):
            return 0
        with io.open(path, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                if r.get("new_path") and r.get("original_path"):
                    self.pinned[r["original_path"].lower()] = r["new_path"]
        return len(self.pinned)

    def load_pathmap(self, path):
        """Freeze every folder already placed: its name on the NAS never changes."""
        if not path or not os.path.exists(path):
            return 0
        with io.open(path, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                self.fixed[r["node_key"]] = r["rendered"]
        return len(self.fixed)

    def pathmap_rows(self):
        return [{"node_key": k, "rendered": v} for k, v in sorted(self.nodes.items())]

    # -- rendering ----------------------------------------------------------------------------
    @staticmethod
    def node_key(drive, segs, i):
        """Stable identity of folder segs[i]: the drive + its full original path."""
        return f"{drive}:" + "\\".join(n for n, _k in segs[: i + 1])

    @staticmethod
    def _next_keep(current, plain):
        """The gentlest keep level, harder than `current` (None = not yet short), that actually makes
        `plain` shorter than it is now; None if no level does."""
        now = len(short_name(plain, current)) if current else len(plain)
        for k in KEEP_LEVELS:
            if (current is None or k < current) and len(short_name(plain, k)) < now:
                return k
        return None

    def _label_roots(self, items):
        """Root label per root folder: its own name (an archive root: its stem); " (2)", " (3)" for a
        second, third different root of the same name in the same tag (sorted by original path)."""
        taken = {}
        for nk, rendered in self.fixed.items():
            parts = rendered.split("\\")
            if len(parts) == 2:
                taken[(parts[0], parts[1].lower())] = nk
        want = {}
        for it in items:
            ri = it.extra["ri"]
            if ri is None:
                continue
            segs = it.extra["segs"]
            nk = self.node_key(it.drive, segs, ri)
            name, kind = segs[ri]
            want[(TAGS[it.drive], nk)] = os.path.splitext(name)[0] if kind == "archive" else name
        for (tag, nk), base in sorted(want.items(), key=lambda kv: kv[0][1].lower()):
            if nk in self.fixed:
                self.roots[(tag, nk)] = self.fixed[nk].split("\\", 1)[1]
                continue
            label, n = base, 1
            while taken.get((tag, label.lower()), nk) != nk:
                n += 1
                label = f"{base} ({n})"
            taken[(tag, label.lower())] = nk
            self.roots[(tag, nk)] = label

    def _walk(self, it, record=False):
        """Render one item. -> (path below base, [(node key, plain rendered name or None if fixed)]).
        With record=True also store every folder's rendered path in self.nodes."""
        segs, ri = it.extra["segs"], it.extra["ri"]
        tag = TAGS[it.drive]
        cur = tag
        nodes = []
        prev_stem = None
        for i in range((ri if ri is not None else 0), len(segs) - 1):
            name, kind = segs[i]
            nk = self.node_key(it.drive, segs, i)
            stem = os.path.splitext(name)[0].lower() if kind == "archive" else None
            if nk in self.fixed:
                cur = self.fixed[nk]
                nodes.append((nk, None))
            elif prev_stem is not None and name.lower() == prev_stem:
                pass                                   # an archive's repeated top folder: not repeated
            else:
                if ri is not None and i == ri:
                    plain = self.roots[(tag, nk)]
                elif kind == "archive":
                    plain = archive_folder_name(name)
                else:
                    plain = name
                cur = f"{cur}\\{short_name(plain, self.short[nk]) if nk in self.short else plain}"
                nodes.append((nk, plain))
            if record:
                self.nodes[nk] = cur
            prev_stem = stem
        fname = segs[-1][0]
        if it.id in self.file_short:
            fname = short_file(fname, self.file_short[it.id])
        return f"{cur}\\{fname}", nodes

    def _longest_first(self, length, node_files, plain_of, top_nodes, by_id, full):
        """Strategy "longest": the worst file first; for it, cut its LONGEST folder name (to that
        folder's next level; a study / top folder only to 24), the cut applying to everything in that
        folder; repeat until it fits; its file name only when no folder can give."""
        def cur(nk):
            k = self.short.get(nk)
            return len(short_name(plain_of[nk], k)) if k else len(plain_of[nk])
        file_nodes = {}
        for nk, fs in node_files.items():
            for f in fs:
                file_nodes.setdefault(f, []).append(nk)
        for f in sorted(length, key=lambda f: (-length[f], f)):
            for _guard in range(512):
                if length[f] <= self.budget:
                    break
                cand = []
                for nk in file_nodes.get(f, ()):
                    nxt = self._next_keep(self.short.get(nk), plain_of[nk])
                    if nxt is None or (nk in top_nodes and nxt != KEEP_LEVELS[0]):
                        continue
                    # a gentle cut before a 6-char one, a sub-folder before the study folder, then longest
                    cand.append((nxt != KEEP_LEVELS[-1], nk not in top_nodes, cur(nk), nk, nxt))
                if cand:
                    _harsh_ok, _nt, _l, nk, nxt = max(cand)
                    if nxt == KEEP_LEVELS[-1]:
                        cand = None                     # a 6-char folder cut only after the file name
                    else:
                        save = cur(nk) - len(short_name(plain_of[nk], nxt))
                        self.short[nk] = nxt
                        for g in node_files[nk]:
                            length[g] -= save
                        continue
                stem = os.path.splitext(by_id[f].extra["segs"][-1][0])[0]
                keep = self.file_short.get(f)
                nxt = self._next_keep(keep, stem)
                if nxt is not None:
                    length[f] -= (len(short_name(stem, keep)) if keep else len(stem)) - len(short_name(stem, nxt))
                    self.file_short[f] = nxt
                    continue
                six = [nk for nk in file_nodes.get(f, ()) if nk not in top_nodes
                       and self._next_keep(self.short.get(nk), plain_of[nk]) == KEEP_LEVELS[-1]]
                if six:
                    nk = max(six, key=lambda n: (cur(n), n))
                    save = cur(nk) - len(short_name(plain_of[nk], KEEP_LEVELS[-1]))
                    self.short[nk] = KEEP_LEVELS[-1]
                    for g in node_files[nk]:
                        length[g] -= save
                    continue
                raise BudgetError(f"cannot bring under {self.budget}: {full(self._walk(by_id[f])[0])}")

    def plan(self, items):
        """-> {item id: destination path from the NAS root}.

        Shortening is a GLOBAL greedy over the whole tree, so the fewest names are cut: each step
        takes the one cut that removes the most total excess (sum, over the over-budget files it
        touches, of min(characters saved, that file's excess)), in tiers:
          1. folders, each to its next level (24, then 12 characters); a study / top folder only
             ever to 24 -- its name carries the protocol number;
          2. file names at 24, only for files the folders could not fix;
          3. sub-folders at 6, then file names at 12 and 6.
        Ties: the gentler cut, then a sub-folder before the study / top folder, then the longer name.
        Raises BudgetError if a file cannot be brought under the budget, a component is over 255,
        or two different originals would land on one path (case-insensitive)."""
        for it in items:
            segs = logical_segments(it.relpath, it.archive, it.member)
            it.extra["segs"] = segs
            it.extra["ri"] = root_index_for(segs, {it.root}) if it.root else None
        self._label_roots(items)
        full = lambda rel: f"{self.base}\\{rel}"  # noqa: E731
        length, node_files, plain_of, top_nodes, by_id = {}, {}, {}, set(), {}
        for it in items:
            pin = self.pinned.get(original_display(it.drive, it.relpath, it.archive, it.member).lower())
            it.extra["pinned"] = pin
            if pin:
                continue                                  # already on the NAS: its path is final
            rel, nodes = self._walk(it)
            by_id[it.id] = it
            length[it.id] = unc_len(full(rel))
            ri = it.extra["ri"]
            top_nodes.add(self.node_key(it.drive, it.extra["segs"], ri if ri is not None else 0))
            for nk, plain in nodes:
                if plain is not None:                     # frozen folders are never candidates
                    node_files.setdefault(nk, []).append(it.id)
                    plain_of[nk] = plain

        def cur_len(name, keep):
            return len(short_name(name, keep)) if keep else len(name)

        def folder_step(levels, top=True):
            """Apply the best folder cut whose next level is in `levels` (study / top folders only if
            `top`); False if none helps."""
            excess = {f: length[f] - self.budget for f in length if length[f] > self.budget}
            best = None
            for nk in {nk for f in excess for nk in self._file_nodes.get(f, ())}:
                keep = self.short.get(nk)
                nxt = self._next_keep(keep, plain_of[nk])
                if nxt is None or nxt not in levels or (nk in top_nodes and (not top or nxt != KEEP_LEVELS[0])):
                    continue                            # a study / top folder: only ever the 24-char cut
                save = cur_len(plain_of[nk], keep) - len(short_name(plain_of[nk], nxt))
                gain = sum(min(save, excess[f]) for f in node_files[nk] if f in excess)
                if gain <= 0:
                    continue
                key = (gain, nxt, nk not in top_nodes, len(plain_of[nk]), nk)
                if best is None or key > best[0]:
                    best = (key, nk, nxt, save)
            if best is None:
                return False
            _k, nk, nxt, save = best
            self.short[nk] = nxt
            for f in node_files[nk]:
                length[f] -= save
            return True

        def file_step(level):
            """Cut, at `level`, the file name of every file still over budget that it helps."""
            done = False
            for f in [f for f in length if length[f] > self.budget]:
                stem = os.path.splitext(by_id[f].extra["segs"][-1][0])[0]
                keep = self.file_short.get(f)
                nxt = self._next_keep(keep, stem)
                if nxt == level:
                    length[f] -= cur_len(stem, keep) - len(short_name(stem, nxt))
                    self.file_short[f] = nxt
                    done = True
            return done

        self._file_nodes = {}
        for nk, fs in node_files.items():
            for f in fs:
                self._file_nodes.setdefault(f, []).append(nk)
        if self.strategy == "gain":
            while any(v > self.budget for v in length.values()):
                # by GAIN (most excess removed per cut): folders at 24 or 12 (a study / top folder
                # only at 24) -> file names at 24 -> sub-folders at 6 -> file names at 12, 6
                if (folder_step({24, 12}) or file_step(24) or folder_step({6}, top=False)
                        or file_step(12) or file_step(6)):
                    continue
                worst = max(length, key=length.get)
                raise BudgetError(f"cannot bring under {self.budget}: {full(self._walk(by_id[worst])[0])}")
        else:
            self._longest_first(length, node_files, plain_of, top_nodes, by_id, full)
        self.nodes = dict(self.fixed)
        out, seen = {}, {}
        for it in items:
            rel, nodes = self._walk(it, record=True)
            if it.extra.get("pinned"):
                rel = it.extra["pinned"]
                it.extra["shortened"] = bool(re.search(r"~[0-9a-f]{4}(\\|\.|$)", rel))
            else:
                it.extra["shortened"] = bool(it.id in self.file_short) or any(
                    nk in self.short or (plain is None and re.search(r"~[0-9a-f]{4}$", self.fixed[nk]))
                    for nk, plain in nodes)
            dest = full(rel)
            if unc_len(dest) > self.budget:
                raise BudgetError(f"over budget after shortening: {dest}")
            if any(len(c) > COMPONENT_MAX for c in dest.split("\\")):
                raise BudgetError(f"a component is over {COMPONENT_MAX}: {dest}")
            k = dest.lower()
            if seen.get(k, it.id) != it.id:
                raise BudgetError(f"two different originals on one destination: {dest}")
            seen[k] = it.id
            out[it.id] = dest
        return out

    # -- what was dropped above each root (for _ORIGIN.txt) -------------------------------------
    def origins(self, items):
        """{rendered root folder (tag\\label): [full original path of that root folder, ...]}"""
        out = {}
        for it in items:
            ri = it.extra.get("ri")
            if ri is None:
                continue
            segs = it.extra["segs"]
            nk = self.node_key(it.drive, segs, ri)
            parts = []
            for n, k in segs[: ri + 1]:
                parts.append(n + NESTED_SEP if k == "archive" else n)
            orig = DRIVE_LABELS[it.drive] + "\\" + "\\".join(parts).replace(NESTED_SEP + "\\", NESTED_SEP)
            out.setdefault(self.nodes.get(nk) or f"{TAGS[it.drive]}\\{self.roots[(TAGS[it.drive], nk)]}",
                           set()).add(orig)
        return {k: sorted(v) for k, v in out.items()}


# --------------------------------------------------------------------------- index / readme / origin

INDEX_FIELDS = ["new_path", "drive", "archive", "original_path", "size", "sha256", "claim_id", "shortened",
                "why", "note"]


def index_rows(dests, items, base):
    """_INDEX.csv rows: paths relative to the tree base, the full original path, and Y where a
    folder or the file name on the way was shortened."""
    rows = []
    for it in items:
        d = dests[it.id]
        rel = d[len(base) + 1:]
        orig = original_display(it.drive, it.relpath, it.archive, it.member)
        rows.append({"new_path": rel, "drive": DRIVE_LABELS[it.drive], "archive": it.archive,
                     "original_path": orig, "size": it.extra.get("size", ""),
                     "sha256": it.extra.get("sha256", ""), "claim_id": it.extra.get("claim_id", ""),
                     "shortened": "Y" if it.extra.get("shortened") else "N",
                     "why": it.extra.get("why", ""), "note": ""})
    return sorted(rows, key=lambda r: r["new_path"].lower())


def write_index(path, rows):
    """UTF-8 WITH a BOM so Excel shows the accents."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with io.open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=INDEX_FIELDS)
        w.writeheader()
        w.writerows(rows)


def write_pathmap(path, rows):
    with io.open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["node_key", "rendered"])
        w.writeheader()
        w.writerows(rows)


PROJECT_README = """\
Historical drive material for this project
==========================================

What this folder is
  Files from the lab's historical external drives that belong to this project
  but are not raw acquisitions: exported images (.tif), figures, slides,
  documents, analysis files, segmentations and derived image volumes (NIfTI,
  MetaImage), scale-bar copies. The raw acquisitions themselves are not here:
  gjesus3 registers them in its archive, and links each registered one in this
  project's raw_linked\\ folder.

  Each drive has its own folder here (only the drives that held material for
  this project appear):
    FRIO-X6\\       operator drive FRIO X6, serial 2322E4A111E7
    MFB-Disco-2\\   operator drive MFB Disco 2, serial 2322E4A112BD
    MJesus-MFB\\    a researcher's working drive (WD My Passport, serial
                   WX22D623YP29, labelled MJesus-MFB-biomaGUNE)

The folder names were shortened
  Windows cannot open very long paths, so:
    - the folders ABOVE each study folder (the drive's own top folders, the
      researcher's folder, the name of a .zip/.7z archive) were left out;
      _ORIGIN.txt inside each study folder says what they were;
    - a .zip or .7z became a normal folder named like Manon_zip;
    - a few very long folder or file names were cut to 24 characters plus a
      short code, for example  Comparasion expiration v~3f2a.
  Nothing was lost. No file was changed: every file is a byte-for-byte copy.

How to find where a file came from
  Open _INDEX.csv in Excel. Each row is one file: its path here (new_path),
  where it was on the drive (original_path), its size and checksum. Use
  Search (Ctrl+F) or a filter on any column.

The originals
  The originals remain on the owners' external drives. Questions: the Data
  Office.

_PATHMAP.csv is for the Data Office (it keeps folder names stable when more
material is added later). Please do not edit it.
"""

# A note for ONE project's tree, appended to PROJECT_README (every other tree keeps the text above, byte for
# byte). The researchers' answers of 2026-10-08 (questions about drive 3, A2/A3): the 0522, 0619 and 0424
# masks were revised by Jesus and Irene, and the revised versions live in a shared OneDrive folder, not on
# the drive; in 0522's 2023 masks, `IRE` marks Irene's corrections of the drive owner's masks.
_MASKS_DRAFT = """
Segmentation masks under MJesus-MFB\\ are drafts
  The segmentation masks of protocol {code} under MJesus-MFB\\ are working
  drafts from the drive. Jesus Ruiz-Cabello and Irene Fernandez later revised
  them; the revised versions are in their shared OneDrive folder, not here.
  Use the masks here as work in progress, not as final results.
"""
_IRE_CORRECTIONS = """\
  In the 2023 masks, the files labelled IRE are Irene's corrections of the
  drive owner's masks (not a second, independent reading).
"""
# The fourth drive-3 batch (tasks/drive3_foreign_raw_gate.md): the Leica confocal files of protocol 1121 are raw
# images that gjesus3 does not register (no .lif reader or instrument code); Irene, 2026-10-08: the Leica TCS SP8 was
# biomaGUNE's own microscope, not the London partner's.
_LEICA_NOT_REGISTERED = """
Raw Leica confocal files under MJesus-MFB\\ (not registered)
  The .lif and .lifext files under MJesus-MFB\\Proyecto 1121 London\\
  Experimentos\\Histologia\\ are raw confocal images from biomaGUNE's former
  Leica TCS SP8 microscope (serial 8100000207). They are kept here, byte for
  byte, as project material: gjesus3 does not register them, because it has
  no reader for Leica .lif files and no instrument code for that microscope.
  The .png files named after a .lif are exports made from it.
"""
PROJECT_README_NOTES = {
    "AE-biomaGUNE-0522": _MASKS_DRAFT.format(code="0522") + _IRE_CORRECTIONS,
    "AE-biomaGUNE-0619": _MASKS_DRAFT.format(code="0619"),
    "AE-biomaGUNE-0424": _MASKS_DRAFT.format(code="0424"),
    "AE-biomaGUNE-1121": _LEICA_NOT_REGISTERED,
}


def project_readme(base=""):
    """README.txt of one project tree (`projects\\<folder>\\working\\historical_drives`): PROJECT_README, plus
    that project's note if it has one (PROJECT_README_NOTES). Any other base gets PROJECT_README unchanged."""
    parts = base.split("\\")
    note = PROJECT_README_NOTES.get(parts[1]) if len(parts) > 1 and parts[0] == "projects" else None
    return PROJECT_README + note if note else PROJECT_README


def origin_text(origs):
    lines = ["Where this folder came from", "===========================", "",
             "This folder is the study folder below. The folders above it on the drive",
             "were left out to keep paths short. Its full original location:", ""]
    lines += [f"  {o}" for o in origs]
    lines += ["", "See ..\\..\\_INDEX.csv for every file's original path.", ""]
    return "\r\n".join(lines)


# ------------------------------------------------------------------------------------------- cli

def main(argv=None):
    ap = argparse.ArgumentParser(description="destination for one historical-drive file")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("dest")
    d.add_argument("--base", required=True, help=r"e.g. projects\AE-biomaGUNE-0721\working\historical_drives")
    d.add_argument("--drive", required=True, choices=sorted(TAGS))
    d.add_argument("--relpath", required=True, help="loose relpath, or the archive relpath for a member")
    d.add_argument("--archive", default="")
    d.add_argument("--member", default="")
    d.add_argument("--root", default="", help="claim root as in claims.csv (the study folder); omit to keep the full path")
    d.add_argument("--pathmap", default="", help="the tree's existing _PATHMAP.csv (keeps placed folders' names)")
    a = ap.parse_args(argv)
    p = Planner(a.base)
    n = p.load_pathmap(a.pathmap)
    it = Item(id="1", drive=a.drive, relpath=a.relpath, archive=a.archive, member=a.member,
              root=claim_root_segments(a.root) if a.root else None)
    dest = p.plan([it])["1"]
    print(dest)
    print(f"# {unc_len(dest)} chars on \\\\GJESUS3\\gjesus3\\ (budget {BUDGET}); frozen folders read: {n}",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
