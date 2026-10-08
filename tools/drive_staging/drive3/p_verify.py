#!/usr/bin/env python3
"""p_verify.py -- stream P: before and after a copy window of the drive-3 non-raw placement.

READ-ONLY on the NAS. Record: tasks/drive3_placement_gate.md.

    snapshot  BEFORE a window: copy every document the window may rewrite -- each target tree's _INDEX.csv
              (the holding folder's manifest.csv), _PATHMAP.csv, README.txt and _ORIGIN.txt files, and each
              target project's provenance.csv -- to a fresh off-NAS folder, in the NAS's own layout, with
              _snapshot.csv listing them (size, SHA-256) and the SHA-256 of every file in registries\\.
              It is the window's dated off-NAS backup AND the "before" state `verify` compares against.
              (Because it keeps the NAS layout, a snapshot folder can also serve as a rehearsal NAS root.)
    verify    AFTER the window: each target tree's MJesus-MFB\\ folder walked against the manifest (0 missing,
              0 extra, 0 size mismatches, no temp files); every BEFORE index row, _PATHMAP.csv entry,
              _ORIGIN.txt line and provenance row still there, unchanged; the new index rows and provenance
              rows there, once each; README.txt the current text; registries\\ unchanged; a re-hash.

    raw-dedup BEFORE the windows, against LIVE production: every registered acquisition's checksums.json
              (an acquisition without one is hashed file by file), so no file the manifest copies or holds
              is already an acquisition file in /raw/. --write-index keeps the live index it built, for
              `p_plan.py handover --raw-index`.

    python tools/drive_staging/drive3/p_verify.py snapshot  --manifest M [--project P ...] [--holding] --nas ROOT --to DIR
    python tools/drive_staging/drive3/p_verify.py verify    --manifest M [--project P ...] [--holding] --nas ROOT --snapshot DIR [--rehash all|sample|none]
    python tools/drive_staging/drive3/p_verify.py raw-dedup --manifest M --nas ROOT [--write-index CSV] [--since YYYY-MM-DD]

With neither --project nor --holding, the scope is every project with place rows, plus the holding folder.
"""
import argparse
import collections
import csv
import hashlib
import io
import os
import random
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.dirname(HERE)
TOOLS = os.path.dirname(DS)
for _p in (TOOLS, DS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import historical_paths as H  # noqa: E402
import nonraw_placement as NP  # noqa: E402

TAG_DIRS = tuple(H.TAGS.values())
SNAP = "_snapshot.csv"
EXISTING = "_existing_MJesus-MFB_files.csv"


def lp(p):
    return NP.lp(p)


def sha256_file(path):
    return NP.sha256_file(path)


def read_csv(path):
    """(rows, header) of a CSV (utf-8 with or without BOM), or ([], []) if absent."""
    if not os.path.exists(lp(path)):
        return [], []
    with io.open(lp(path), encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        return list(r), list(r.fieldnames or [])


def scope(manifest_rows, projects_arg, holding_arg):
    """-> (projects in scope, holding in scope?)"""
    place_projects = sorted({r["project_name"] for r in manifest_rows if r["decision"] == "place"})
    if not projects_arg and not holding_arg:
        return place_projects, any(r["decision"] == "holding" for r in manifest_rows)
    return sorted(projects_arg or []), bool(holding_arg)


def tree_of(project, projects):
    if project is None:
        return NP.HOLDING_BASE
    return "\\".join(["projects", NP.project_folder(project, projects), *NP.SUBDIR])


def tree_docs(nas, base, holding):
    """NAS-relative paths of the documents a publish may rewrite in one tree."""
    out = [f"{base}\\{'manifest.csv' if holding else H.INDEX_NAME}", f"{base}\\{H.PATHMAP_NAME}",
           f"{base}\\{H.README_NAME}"]
    root = os.path.join(nas, base)
    if not holding and os.path.isdir(lp(root)):
        for tag in sorted(os.listdir(lp(root))):
            tdir = os.path.join(root, tag)
            if tag not in TAG_DIRS or not os.path.isdir(lp(tdir)):
                continue
            for sub in sorted(os.listdir(lp(tdir))):
                if os.path.exists(lp(os.path.join(tdir, sub, H.ORIGIN_NAME))):
                    out.append(f"{base}\\{tag}\\{sub}\\{H.ORIGIN_NAME}")
    return out


def cmd_snapshot(args):
    rows = NP.load_manifest(args.manifest)
    projects = NP.load_projects(args.nas)
    projs, hold = scope(rows, args.project, args.holding)
    if os.path.isdir(args.to) and os.listdir(args.to):
        print(f"REFUSED: {args.to} exists and is not empty (use a fresh, dated folder)")
        return 2
    os.makedirs(args.to, exist_ok=True)
    listing = []

    def save(rel, kind):
        src = os.path.join(args.nas, rel)
        if not os.path.exists(lp(src)):
            listing.append({"rel": rel, "kind": kind, "size": "", "sha256": "", "present": "N"})
            return
        dst = os.path.join(args.to, rel)
        os.makedirs(lp(os.path.dirname(dst)), exist_ok=True)
        shutil.copyfile(lp(src), lp(dst))
        listing.append({"rel": rel, "kind": kind, "size": os.path.getsize(lp(dst)), "sha256": sha256_file(dst),
                        "present": "Y"})

    existing = []   # files ALREADY under <tree>\MJesus-MFB\ (an earlier batch): verify must not call them extra
    for p in projs:
        pdir = "\\".join(["projects", NP.project_folder(p, projects)])
        os.makedirs(lp(os.path.join(args.to, pdir)), exist_ok=True)   # the rehearsal needs the folder
        save(f"{pdir}\\provenance.csv", "provenance")
        for rel in tree_docs(args.nas, tree_of(p, projects), False):
            save(rel, "tree-doc")
        existing += [{"rel": k, "size": v} for k, v in walk_tag(args.nas, tree_of(p, projects)).items() if is_data(k)]
    if hold:
        for rel in tree_docs(args.nas, NP.HOLDING_BASE, True):
            save(rel, "tree-doc")
        existing += [{"rel": k, "size": v} for k, v in walk_tag(args.nas, NP.HOLDING_BASE).items() if is_data(k)]
    NP.wcsv(os.path.join(args.to, EXISTING), ["rel", "size"], existing)
    reg = os.path.join(args.nas, "registries")
    for name in sorted(os.listdir(lp(reg))):
        full = os.path.join(reg, name)
        if not os.path.isfile(lp(full)) or name.startswith("."):
            continue
        if name == "registry_projects.csv":
            save(f"registries\\{name}", "registry-copied")
        else:
            listing.append({"rel": f"registries\\{name}", "kind": "registry-hash", "size": os.path.getsize(lp(full)),
                            "sha256": sha256_file(full), "present": "Y"})
    NP.wcsv(os.path.join(args.to, SNAP), ["rel", "kind", "size", "sha256", "present"], listing)
    n = collections.Counter(x["kind"] for x in listing if x["present"] == "Y")
    print(f"snapshot: {len(projs)} projects{' + holding' if hold else ''}; saved {dict(n)}; "
          f"absent {sum(1 for x in listing if x['present'] == 'N')}; already under {H.TAGS['D3']}\\: "
          f"{len(existing)} files -> {args.to}")
    return 0


def expected_rows(rows, projs, hold, projects):
    """{tree base: {dest_rel: manifest row}} for the window's scope."""
    out = collections.defaultdict(dict)
    for r in rows:
        if r["decision"] == "place" and r["project_name"] in projs:
            out[tree_of(r["project_name"], projects)][r["dest_rel"]] = r
        elif r["decision"] == "holding" and hold:
            out[NP.HOLDING_BASE][r["dest_rel"]] = r
    return out


def walk_tag(nas, base):
    """Every file under <base>\\MJesus-MFB\\ -> {NAS-relative path: size}."""
    out = {}
    root = os.path.join(nas, base, H.TAGS["D3"])
    if not os.path.isdir(lp(root)):
        return out
    pre = len(lp(nas).rstrip("\\")) + 1
    for d, _ds, fs in os.walk(lp(root)):
        for f in fs:
            full = os.path.join(d, f)
            out[full[pre:]] = os.path.getsize(full)
    return out


def is_temp(name):
    return (name.startswith(".~nonraw-") and name.endswith(".part")) or name.endswith(".~nonraw.tmp")


def is_data(rel):
    """A placed data file, not one of the tool's own documents (which a later batch may rewrite) or a temp."""
    name = os.path.basename(rel)
    return name not in (H.ORIGIN_NAME, NP.NOTREG_README) and not is_temp(name)


def cmd_verify(args):
    rows = NP.load_manifest(args.manifest)
    projects = NP.load_projects(args.nas)
    projs, hold = scope(rows, args.project, args.holding)
    snap = {x["rel"]: x for x in csv.DictReader(io.open(os.path.join(args.snapshot, SNAP), encoding="utf-8", newline=""))}
    before_files, _ = read_csv(os.path.join(args.snapshot, EXISTING))   # an earlier batch's files in these trees
    before_files = {x["rel"].lower(): int(x["size"]) for x in before_files}
    exp = expected_rows(rows, projs, hold, projects)
    fails = []
    tot = collections.Counter()

    def ok(cond, msg):
        print(f"  {'PASS' if cond else 'FAIL'}  {msg}")
        if not cond:
            fails.append(msg)

    trees = [(p, tree_of(p, projects)) for p in projs] + ([(None, NP.HOLDING_BASE)] if hold else [])
    for proj, base in trees:
        holding = proj is None
        want = exp.get(base, {})
        print(f"\n== {base}  ({len(want)} files expected)")
        have = walk_tag(args.nas, base)
        docs = {k for k in have if os.path.basename(k) in (H.ORIGIN_NAME, NP.NOTREG_README)}
        temps = [k for k in have if is_temp(os.path.basename(k))]
        data = {k: v for k, v in have.items() if k not in docs and k not in temps}
        low = {k.lower(): k for k in data}
        missing = [d for d in want if d.lower() not in low]
        wl = {d.lower() for d in want}
        mine_before = {k: v for k, v in before_files.items() if k.startswith(base.lower() + "\\")}
        extra = [k for k in data if k.lower() not in wl and k.lower() not in mine_before]
        size_bad = [d for d in want if d.lower() in low and data[low[d.lower()]] != int(want[d]["size"])]
        gone = [k for k, v in mine_before.items() if k not in low or data[low[k]] != v]
        ok(not missing and not extra and not size_bad and not temps and not gone,
           f"walk: {len(data)} files on the NAS ({len(mine_before)} there before the window); missing {len(missing)}, "
           f"extra {len(extra)}, size mismatches {len(size_bad)}, temp files {len(temps)}, earlier files changed "
           f"or gone {len(gone)}")
        for x in (missing + extra + size_bad + temps + gone)[:10]:
            print(f"        {x}")
        tot["files"] += len(want)
        tot["bytes"] += sum(int(r["size"]) for r in want.values())
        # the index: every BEFORE row unchanged, every new row present once, nothing else
        iname = "manifest.csv" if holding else H.INDEX_NAME
        after, _h = read_csv(os.path.join(args.nas, base, iname))
        before, bh = read_csv(os.path.join(args.snapshot, base, iname))
        akey = collections.Counter(((r.get("new_path") or "").lower(), (r.get("original_path") or "").lower()) for r in after)
        aset = {((r.get("new_path") or "").lower(), (r.get("original_path") or "").lower()): r for r in after}
        lost = [b for b in before if aset.get(((b.get("new_path") or "").lower(), (b.get("original_path") or "").lower())) is None
                or any((aset[((b.get("new_path") or "").lower(), (b.get("original_path") or "").lower())].get(c) or "")
                       != (b.get(c) or "") for c in bh)]
        new_ok = 0
        for d, r in want.items():
            k = (d[len(base) + 1:].lower(), H.original_display(r["drive"], r["relpath"], r["archive"], r["member"]).lower())
            a = aset.get(k)
            if a is not None and a.get("sha256") == r["sha256"] and str(a.get("size")) == str(r["size"]):
                new_ok += 1
        dupk = [k for k, n in akey.items() if n > 1]
        ok(not lost and new_ok == len(want) and len(after) == len(before) + len(want) and not dupk,
           f"{iname}: {len(before)} rows before, all kept unchanged ({len(before) - len(lost)}); "
           f"{new_ok}/{len(want)} new rows present with size and SHA-256; {len(after)} after "
           f"(= {len(before)} + {len(want)}: {'yes' if len(after) == len(before) + len(want) else 'NO'}); duplicates {len(dupk)}")
        # _PATHMAP.csv: before entries kept, with the same rendered names
        pa, _ = read_csv(os.path.join(args.nas, base, H.PATHMAP_NAME))
        pb, _ = read_csv(os.path.join(args.snapshot, base, H.PATHMAP_NAME))
        pam = {r["node_key"]: r["rendered"] for r in pa}
        plost = [r for r in pb if pam.get(r["node_key"]) != r["rendered"]]
        d3 = sum(1 for k in pam if k.startswith("D3:"))
        ok(not plost and d3 > 0, f"_PATHMAP.csv: {len(pb)} entries before, all kept ({len(pb) - len(plost)}); "
                                 f"{d3} MJesus-MFB folders recorded")
        # _ORIGIN.txt: every before origin line kept
        olost = 0
        for rel, x in snap.items():
            if rel.startswith(base + "\\") and rel.endswith(H.ORIGIN_NAME) and x["present"] == "Y":
                b = NP._origins_in(io.open(lp(os.path.join(args.snapshot, rel)), encoding="utf-8", errors="replace").read())
                a = NP._origins_in(io.open(lp(os.path.join(args.nas, rel)), encoding="utf-8", errors="replace").read()) \
                    if os.path.exists(lp(os.path.join(args.nas, rel))) else []
                olost += len(set(b) - set(a))
        ok(olost == 0, f"_ORIGIN.txt: every before origin line kept (lost {olost})")
        # README.txt: the current text
        want_readme = (NP.README_TXT if holding else H.project_readme(base)).replace("\n", "\r\n").encode("utf-8")
        rp = os.path.join(args.nas, base, H.README_NAME)
        ok(os.path.exists(lp(rp)) and open(lp(rp), "rb").read() == want_readme, "README.txt is the current text")
        # provenance.csv (projects): before rows unchanged, one row per new file, no duplicate output_path
        if not holding:
            prel = "\\".join(["projects", NP.project_folder(proj, projects), "provenance.csv"])
            pafter, _ = read_csv(os.path.join(args.nas, prel))
            pbefore, ph = read_csv(os.path.join(args.snapshot, prel))
            same_prefix = all(all((pafter[i].get(c) or "") == (pbefore[i].get(c) or "") for c in ph)
                              for i in range(len(pbefore))) if len(pafter) >= len(pbefore) else False
            pfx = "\\".join(base.split("\\")[:2]) + "\\"
            added = pafter[len(pbefore):]
            outs = collections.Counter(r.get("output_path") for r in added)
            outs_before = {r.get("output_path") for r in pbefore}
            missing_p = [d for d in want if outs.get(d[len(pfx):].replace("\\", "/"), 0) != 1]
            # judged on the rows THIS window added: once each, never over an earlier row. Production files
            # already repeat some output_path (an ingest link and its later retirement): not ours, counted only
            dupo = [k for k, n in outs.items() if n > 1 or k in outs_before]
            pre = sum(1 for n in collections.Counter(r.get("output_path") for r in pbefore).values() if n > 1)
            ids = collections.Counter(r.get("file_id") for r in added)
            old_ids = {r.get("file_id") for r in pbefore}
            dup_ids = [k for k, n in ids.items() if n > 1 or k in old_ids]
            ok(same_prefix and not missing_p and not dupo and not dup_ids,
               f"provenance.csv: {len(pbefore)} rows before kept unchanged ({'yes' if same_prefix else 'NO'}); "
               f"{len(want) - len(missing_p)}/{len(want)} files have one row; added rows repeating an output_path "
               f"{len(dupo)}, repeating a file_id {len(dup_ids)}; {len(added)} rows added"
               + (f" (the file already repeated {pre} output_paths before the window: not this window's)" if pre else ""))
        # re-hash
        if args.rehash != "none":
            pool = sorted(d for d in want if d.lower() in low)     # a missing file is already reported above
            if args.rehash == "sample":
                random.seed(args.seed)
                pool = random.sample(pool, max(1, int(len(pool) * args.sample))) if pool else []
            bad = [d for d in pool if sha256_file(os.path.join(args.nas, low[d.lower()])) != want[d]["sha256"]]
            tot["rehashed"] += len(pool)
            ok(not bad and (pool or not want), f"re-hash ({args.rehash}): {len(pool)} files, {len(bad)} mismatches")
    # registries unchanged
    print("\n== registries")
    changed = []
    for rel, x in snap.items():
        if x["kind"] in ("registry-hash", "registry-copied") and x["present"] == "Y":
            full = os.path.join(args.nas, rel)
            if not os.path.exists(lp(full)) or sha256_file(full) != x["sha256"]:
                changed.append(rel)
    ok(not changed, f"registries\\: {sum(1 for x in snap.values() if x['kind'].startswith('registry'))} files, "
                    f"changed since the snapshot: {changed or 'none'}")
    print(f"\n{'VERIFY PASS' if not fails else 'VERIFY FAIL'}: {len(trees)} trees, {tot['files']} files, "
          f"{tot['bytes'] / 1e9:.2f} GB expected; re-hashed {tot['rehashed']}")
    return 1 if fails else 0


RAW_INDEX_FIELDS = ["sha256", "acq_id", "instrument", "project_id", "registration_datetime", "relpath", "source"]
GENERATED = {"checksums.json", "metadata.json", "readme.txt"}   # written by the ingest, not drive content


def live_raw_index(nas, say=print):
    """Every file of every registered acquisition, read LIVE from production: the acquisition folder
    (registry_raw.csv canonical_path) -> its checksums.json; an acquisition without one is hashed file by
    file (its generated README.txt / metadata.json skipped). -> rows of RAW_INDEX_FIELDS. Read-only."""
    import json
    reg, _ = read_csv(os.path.join(nas, "registries", "registry_raw.csv"))
    out, no_folder, hashed = [], [], []
    for i, a in enumerate(reg, 1):
        d = os.path.join(nas, (a.get("canonical_path") or "").strip("/").replace("/", "\\"))
        cj = os.path.join(d, "checksums.json")
        base = {"acq_id": a["acq_id"], "instrument": a.get("instrument", ""), "project_id": a.get("project_id", ""),
                "registration_datetime": a.get("registration_datetime", "")}
        if os.path.exists(lp(cj)):
            with io.open(lp(cj), encoding="utf-8") as f:
                files = json.load(f).get("files", {})
            out += [dict(base, sha256=s, relpath=rel, source="checksums.json") for rel, s in files.items()]
        elif os.path.isdir(lp(d)):
            n0, top = len(out), os.path.normcase(lp(d))
            for dd, _ds, fs in os.walk(lp(d)):
                for name in fs:
                    if name.lower() in GENERATED and os.path.normcase(dd) == top:
                        continue
                    full = os.path.join(dd, name)
                    out.append(dict(base, sha256=sha256_file(full), relpath=full[len(lp(d)) + 1:], source="hashed"))
            hashed.append(f"{a['acq_id']} ({len(out) - n0} files)")
        else:
            no_folder.append(a["acq_id"])
        if i % 5000 == 0:
            say(f"  ... {i}/{len(reg)} acquisitions read")
    say(f"live /raw/ index: {len(reg)} acquisitions in registry_raw.csv; {len(out)} files "
        f"({len({r['sha256'] for r in out})} distinct SHA-256); hashed directly (no checksums.json): "
        f"{hashed or 'none'}; no folder on the NAS: {no_folder or 'none'}")
    return out


def cmd_raw_dedup(args):
    """No file this manifest copies or holds is already an acquisition file in /raw/ (live)."""
    rows = NP.load_manifest(args.manifest)
    idx = live_raw_index(args.nas)
    by_sha = collections.defaultdict(list)
    for x in idx:
        by_sha[x["sha256"]].append(x)
    if args.write_index:
        NP.wcsv(args.write_index, RAW_INDEX_FIELDS, idx)
        print(f"  live index written: {args.write_index}")
    if args.since:
        day = [x for x in idx if x["registration_datetime"][:10] == args.since[:10]]
        print(f"  acquisitions registered on {args.since[:10]}: {len({x['acq_id'] for x in day})}, "
              f"{len(day)} files, by instrument {dict(collections.Counter(x['instrument'] for x in day))}")
    hits = collections.Counter()
    ex = {}
    for r in rows:
        if r["sha256"] in by_sha:
            hits[r["decision"]] += 1
            ex.setdefault(r["decision"], (r["relpath"] + (f"!{r['member']}" if r["member"] else ""),
                                          by_sha[r["sha256"]][0]["acq_id"]))
    copied = sum(hits[d] for d in ("place", "holding", "held"))
    print(f"  manifest rows whose bytes are an acquisition file in /raw/: {dict(hits) or 'none'}")
    for d, (p, a) in sorted(ex.items()):
        print(f"    e.g. {d}: {p} = {a}")
    n = sum(1 for r in rows if r["decision"] in ("place", "holding", "held"))
    print(f"{'RAW-DEDUP PASS' if not copied else 'RAW-DEDUP FAIL'}: {copied} of the {n} rows copied now or held "
          f"are in /raw/ (all {len(rows)} manifest rows checked)")
    return 1 if copied else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    rdd = sub.add_parser("raw-dedup")
    rdd.add_argument("--manifest", required=True)
    rdd.add_argument("--nas", default=NP.NAS_DEFAULT)
    rdd.add_argument("--write-index", default="", help="keep the live index (CSV) for p_plan.py handover --raw-index")
    rdd.add_argument("--since", default="", help="also count the acquisitions registered on this date")
    for name in ("snapshot", "verify"):
        s = sub.add_parser(name)
        s.add_argument("--manifest", required=True)
        s.add_argument("--nas", default=NP.NAS_DEFAULT)
        s.add_argument("--project", nargs="*")
        s.add_argument("--holding", action="store_true")
        if name == "snapshot":
            s.add_argument("--to", required=True)
        else:
            s.add_argument("--snapshot", required=True)
            s.add_argument("--rehash", choices=["all", "sample", "none"], default="sample")
            s.add_argument("--sample", type=float, default=0.02)
            s.add_argument("--seed", type=int, default=20261006)
    args = ap.parse_args(argv)
    return {"snapshot": cmd_snapshot, "verify": cmd_verify, "raw-dedup": cmd_raw_dedup}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
