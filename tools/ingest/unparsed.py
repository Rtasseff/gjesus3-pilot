"""unparsed.py — report every parse target that matched no `filename_parse` rule.

`config.expand_batch` globs the staging area, then runs the config's
`filename_parse` rule (a regex and/or positional fields) on each match's parse
target: the match's own name (`source: name`) or its parent folder's name
(`source: parent_name`, which for Bruker ParaVision is the STUDY folder). A
target the rule cannot parse is dropped, and with it every match under it.

Until 2026-10-05 that drop left only one `[expand_batch] SKIP <exam>: ...` line
per exam on stdout, among thousands, with no count and nothing durable. That is
how a whole study (`jrc250526_145_0522`, the operator omitted the `m`) went
unnoticed for two months (STATUS §0 D3; BACKLOG HIGH 2026-08-21). This module is
the one construction site for the replacement: the record shape, the wording of
the summary, and the CSV.

One record per parse TARGET (for MRI: per study folder), not per match:

    target          the name the rule ran on (study folder name, or file name)
    target_path     the full path of that folder / file
    source          filename_parse.source: "parent_name" | "name"
    rule            "regex" | "positional"
    pattern         the regex, or "separator=<s> fields=[...]"
    reason          the parser's message, verbatim (the same text as the SKIP lines)
    n_matches       glob matches dropped with this target
    n_exam_folders  of those, ParaVision exam folders (`acqp` + `method`, the
                    ingest's own detector) -- the acquisitions actually lost
    matches         their original_name values (staging-relative, forward slashes)
    config          the config that ran (its repo-relative path; "" for an
                    in-memory GUI config)
    staging_dir     the batch root

Deliberately NOT counted here: a `filter:` miss (a deliberate exclusion), a
`path_parse` depth mismatch, a non-scan sibling folder, an already-ingested
match. Those keep their own SKIP lines. Also out of reach: a name the glob never
returns at all (leading-dot names), and a study nested one level deeper than the
pattern (`<study>/Other data/<exam>`, where `parent_name` reads "Other data").
"""

import csv
import fnmatch
import os
from datetime import datetime, timezone

CSV_FIELDS = [
    "kind", "target", "n_exam_folders", "n_matches", "target_path", "source", "rule",
    "reason", "pattern", "config", "staging_dir", "matches", "reported_at",
]


def note(groups, *, target, target_path, source, rule, pattern, reason,
         original_name, is_exam, config="", staging_dir=""):
    """Add one dropped match to `groups` (a dict keyed by target_path).

    The first failure under a target creates its record; later matches under
    the same target only add to its counts.
    """
    rec = groups.get(target_path)
    if rec is None:
        rec = groups[target_path] = {
            "kind": "parse", "target": target, "target_path": target_path, "source": source,
            "rule": rule, "pattern": pattern, "reason": reason,
            "n_matches": 0, "n_exam_folders": 0, "matches": [],
            "config": config or "", "staging_dir": staging_dir or "",
        }
    rec["n_matches"] += 1
    if is_exam:
        rec["n_exam_folders"] += 1
    rec["matches"].append(original_name)
    return rec


def is_unseen(rec):
    return rec.get("kind") in ("hidden", "appledouble")


def split(records):
    """-> (parse_records, unseen_records)."""
    return ([r for r in records if not is_unseen(r)],
            [r for r in records if is_unseen(r)])


def totals(records):
    """-> (n_targets, n_exam_folders, n_matches) over a list of records."""
    return (len(records),
            sum(r["n_exam_folders"] for r in records),
            sum(r["n_matches"] for r in records))


def _unit(records):
    if any(r.get("source") == "parent_name" for r in records):
        return "study folder(s)"
    return "name(s)"


def count_label(rec):
    """'15 exam folders', '15 exam folders + 2 other entries', or '3 matches'."""
    if is_unseen(rec):
        return _UNSEEN_LABEL[rec["kind"]]
    n_ex, n_m = rec["n_exam_folders"], rec["n_matches"]
    if not n_ex:
        return f"{n_m} match{'es' if n_m != 1 else ''}"
    label = f"{n_ex} exam folder{'s' if n_ex != 1 else ''}"
    other = n_m - n_ex
    if other:
        label += f" + {other} other entr{'ies' if other != 1 else 'y'}"
    return label


_UNSEEN_LABEL = {"hidden": "hidden name (never globbed)",
                 "appledouble": "macOS AppleDouble file (ignorable)"}


def headline(records):
    """The one-line count, e.g.
    'NOT PARSED: 3 study folder(s) (31 exam folders) matched no filename_parse rule'.
    """
    records = split(records)[0]
    n, n_ex, n_m = totals(records)
    inner = (f"{n_ex} exam folder{'s' if n_ex != 1 else ''}" if n_ex
             else f"{n_m} match{'es' if n_m != 1 else ''}")
    return f"NOT PARSED: {n} {_unit(records)} ({inner}) matched no filename_parse rule"


def detail_lines(records):
    """One line per target, sorted by name: '<target>  <count>  <path>'."""
    recs = sorted(split(records)[0],
                  key=lambda r: (r["target"].lower(), r["target_path"]))
    width = min(max((len(r["target"]) for r in recs), default=0), 70)
    return [f"{r['target']:<{width}}  {count_label(r)}" for r in recs]


def unseen_headline(records):
    """'NOT SEEN: 3 hidden name(s) (1 macOS AppleDouble) never reached the ingest',
    or '' when there are none."""
    un = split(records)[1]
    if not un:
        return ""
    n_ad = sum(1 for r in un if r["kind"] == "appledouble")
    ad = f" ({n_ad} macOS AppleDouble, ignorable)" if n_ad else ""
    return (f"NOT SEEN: {len(un)} name(s) starting with '.'{ad} never reached "
            f"the ingest (glob does not return them)")


def unseen_detail_lines(records):
    """One line per unseen entry: '<staging-relative path>  <kind label>'."""
    un = sorted(split(records)[1], key=lambda r: r["matches"][0].lower())
    width = min(max((len(r["matches"][0]) for r in un), default=0), 70)
    return [f"{r['matches'][0]:<{width}}  {count_label(r)}" for r in un]


def find_unseen(staging_dir, pattern, config=""):
    """Dot-named entries `glob.glob(staging_dir/pattern)` never returns.

    Walks the staging area plainly (no glob), following the pattern segment by
    segment. A dot-named entry that fnmatch accepts for a segment is reported:
    at the last segment it is the file/folder itself; at an earlier segment it is
    a hidden folder whose contents the glob never reached (reported as that
    folder, contents not listed). Entries the pattern excludes for other reasons
    (an extension, a file where `*/` wants folders) are the pattern doing its
    job and are not reported. Returns records for `unparsed`.
    """
    segs = [s for s in pattern.replace("\\", "/").split("/")]
    dirs_only = bool(segs) and segs[-1] == ""
    segs = [s for s in segs if s != ""]
    out = []
    if not segs:
        return out

    def rec(path, kind, rel):
        is_dir = os.path.isdir(path)
        name = os.path.basename(path)
        return {
            "kind": kind, "target": name, "target_path": path,
            "source": "unseen", "rule": "not globbed", "pattern": pattern,
            "reason": ("macOS AppleDouble companion file (._*); not ingested, "
                       "safe to ignore" if kind == "appledouble" else
                       "name starts with '.', which the glob never returns; "
                       "not ingested" + (" (folder contents not listed)"
                                         if is_dir else "")),
            "n_matches": 1, "n_exam_folders": 0, "matches": [rel],
            "config": config or "", "staging_dir": staging_dir,
        }

    def entries(d):
        try:
            return sorted(os.scandir(d), key=lambda e: e.name)
        except OSError:
            return []

    def walk(d, i):
        seg, last = segs[i], i == len(segs) - 1
        if seg == "**":
            if last:                       # '**' alone: everything below
                seg, last = "*", True
            else:
                walk(d, i + 1)             # zero levels
                for e in entries(d):
                    if os.path.isdir(e.path):
                        if e.name.startswith("."):
                            add(e.path)
                        else:
                            walk(e.path, i)
                return
        for e in entries(d):
            hidden = e.name.startswith(".")
            if not fnmatch.fnmatchcase(e.name, seg):
                continue
            isdir = os.path.isdir(e.path)
            if last:
                if dirs_only and not isdir:
                    continue
                if hidden:
                    add(e.path)
            elif isdir:
                if hidden:
                    add(e.path)
                else:
                    walk(e.path, i + 1)

    def add(path):
        rel = os.path.relpath(path, staging_dir).replace(os.sep, "/")
        kind = "appledouble" if os.path.basename(path).startswith("._") else "hidden"
        out.append(rec(path, kind, rel))

    if os.path.isdir(staging_dir):
        walk(staging_dir, 0)
    return out


def public(records):
    """JSON-safe copies for a front-end (the GUI preview): no long match list."""
    keep = ("kind", "target", "target_path", "source", "rule", "reason",
            "n_matches", "n_exam_folders")
    out = []
    for r in sorted(records, key=lambda r: (r["target"].lower(), r["target_path"])):
        d = {k: r[k] for k in keep}
        if is_unseen(r):                    # one path each: short, and the label
            d["matches"] = list(r["matches"])
        out.append(d)
    return out


def write_csv(records, path):
    """Write the full report to `path` (overwritten; header-only when empty).

    One row per target. `matches` is ';'-joined. Plain UTF-8, CRLF rows (the
    csv module default), so it opens cleanly in Excel. Returns the row count.
    """
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = sorted(records, key=lambda r: (r["target"].lower(), r["target_path"]))
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        w.writeheader()
        for r in rows:
            out = {k: r.get(k, "") for k in CSV_FIELDS}
            out["matches"] = ";".join(r.get("matches") or [])
            out["reported_at"] = stamp
            w.writerow(out)
    return len(rows)
