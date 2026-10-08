#!/usr/bin/env python3
"""closeout_records.py -- the M. Jesus drive's evidence copy: the records that outlive the staged copy and the
D: scratch, copied to the NAS records folder beside drives 1+2's, each file SHA-256-verified. Record:
tasks/drive3_closeout.md ("The evidence copy").

    set PYTHONDONTWRITEBYTECODE=1
    python tools/drive_staging/drive3/closeout_records.py plan   --out PLAN_DIR
    python tools/drive_staging/drive3/closeout_records.py copy   --plan PLAN_DIR\\records_plan.csv [--execute]
    python tools/drive_staging/drive3/closeout_records.py verify --plan PLAN_DIR\\records_plan.csv

plan    READ-ONLY. Lists what goes to J:\\gjesus3-data\\staging\\historical_drives_records\\<DRIVE_DIR>\\ and hashes
        it at the source: the staging run's own records (every file at the top of the staged copy: manifest.csv,
        copy and verify logs, drive_info.txt, run_info.json, errors.csv, ...) and the evidence under
        D:\\projects\\gjesus3\\drive3_analysis\\ and \\drive3_streams\\ (documents only: no image data, no rehearsal
        NAS roots, staging copies, farms, local copies, caches or scratch). Writes records_plan.csv, excluded.csv
        (what is left out, and why) and the README section to PLAN_DIR. Nothing on the NAS is touched.
copy    Without --execute: a dry run (what would be copied; refuses if a destination already holds other bytes).
        With --execute: copies each file (never over another file: an identical one is skipped), re-reads the
        source while copying and the copy afterwards, both must equal the plan's SHA-256; then appends the new
        rows to the records folder's records_manifest.csv (its BOM and CRLF kept, existing rows untouched) and
        the drive-3 section to its README.txt (once).
verify  READ-ONLY. Every planned file is at its destination with the plan's SHA-256 (re-hashed) and is listed
        once in records_manifest.csv with that size and SHA-256.
"""
import argparse
import collections
import csv
import hashlib
import io
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DS = os.path.dirname(HERE)
TOOLS = os.path.dirname(DS)
for _p in (TOOLS, DS, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import nonraw_placement as NP  # noqa: E402

NAS = NP.NAS_DEFAULT
RECORDS = os.path.join(NAS, "staging", "historical_drives_records")
DRIVE_DIR = "drive3_MJesus_WX22D623YP29"
STAGED = r"J:\_staging_drive3_MJ\drive3_MJesus_WX22D623YP29"
SOURCES = (("drive3_analysis", r"D:\projects\gjesus3\drive3_analysis"),
           ("drive3_streams", r"D:\projects\gjesus3\drive3_streams"))
# folders that hold image data or regenerable bulk, never evidence (any depth)
EXCLUDE_DIRS = {"rehearsal": "rehearsal NAS root (copies of production files and drive data)",
                "rehearsal_nas": "rehearsal NAS root (copies of production files and drive data)",
                "stage": "the stream's staging copy of drive files (image data)",
                "farm": "hard links to the staged image files",
                "local": "local copies of the drive's image files",
                "scratch": "scratch",
                "_repair": "a copy of the replaced production file (image data)",
                "_cache": "the analysis's pickle caches (regenerable)"}
DOC_EXT = {".csv", ".log", ".txt", ".json", ".jsonl", ".md", ".out", ".yaml", ".yml", ".py", ".cmd", ".ps1",
           ".sh", ".tsv", ".html", ".xlsx", ".docx", ".pdf"}
DOC_GZ = {".csv.gz", ".log.gz", ".txt.gz", ".json.gz"}
# the D: copy of the drive manifest is byte-identical to the staged one, which is copied
SKIP_FILES = {("drive3_analysis", "drive3_manifest.csv"): "identical to the staged copy's manifest.csv (copied)"}
PLAN_FIELDS = ["source", "dest_rel", "size", "sha256", "group"]
README_MARK = "Third historical drive (M. Jesus)"
README_SECTION = f"""
{README_MARK}
====================================
  {DRIVE_DIR}\\
      M. Jesus's working drive (label MJesus-MFB-biomaGUNE, WD serial WX22D623YP29), on loan from
      2026-09-29 and returned to her; staged on 2026-09-29/30 to J:\\_staging_drive3_MJ\\ (on the NAS,
      outside gjesus3-data), which is deleted once the close-out passes.
      At its top: the staging run's own records -- manifest.csv (the SHA-256 of all 621,969 files),
      copy and verify logs, drive_info.txt, run_info.json, errors.csv. The files themselves are NOT here.
      drive3_analysis\\  the read-only assessment: A1 (raw imaging), A2 (projects and placement),
                         A3 (segmentations), the production index it used, the hub's records snapshot.
      drive3_streams\\   every work stream's evidence: placement manifests and run logs (placement,
                         bmj), the PET/CT, Cell Observer and MRI plans, dry runs and verifications,
                         the workbook backups, and the close-out reconciliation (closeout\\).
  Deliberately NOT kept: the streams' staging copies, rehearsal NAS roots, hard-link farms, local
  copies and caches (image data, regenerable from gjesus3 or the owner's drive).
  Where the data went: /raw/ (registered), the project folders (working\\historical_drives\\MJesus-MFB\\),
  or staging\\historical_drives_unassigned\\MJesus-MFB\\; the rest was ruled out file by file
  (tasks/drive3_closeout.md in the gjesus3-pilot repo).
"""


def lp(p):
    return NP.lp(p)


def sha256_file(path, bufsize=8 << 20):
    h = hashlib.sha256()
    with open(lp(path), "rb") as f:
        for b in iter(lambda: f.read(bufsize), b""):
            h.update(b)
    return h.hexdigest()


def is_doc(name):
    low = name.lower()
    return any(low.endswith(x) for x in DOC_GZ) or os.path.splitext(low)[1] in DOC_EXT


def ext_of(name):
    low = name.lower()
    for x in DOC_GZ:
        if low.endswith(x):
            return x
    return os.path.splitext(low)[1] or "(none)"


def select(staged, sources):
    """-> (plan rows without sha256, excluded rows). Read-only."""
    plan, excl = [], []
    for name in sorted(os.listdir(lp(staged))):
        full = os.path.join(staged, name)
        if os.path.isfile(lp(full)):
            plan.append({"source": full, "dest_rel": f"{DRIVE_DIR}\\{name}", "size": os.path.getsize(lp(full)),
                         "group": "staging run records"})
    for label, root in sources:
        for d, ds, fs in os.walk(lp(root)):
            rel_d = d[len(lp(root)):].lstrip("\\")
            keep = []
            for x in sorted(ds):
                why = EXCLUDE_DIRS.get(x.lower()) or ("this evidence plan itself (records_manifest.csv lists the same)"
                                                      if x.lower().startswith("records_plan") else "")
                if why:
                    n = b = 0
                    for dd, _dds, ffs in os.walk(os.path.join(d, x)):
                        for f in ffs:
                            n += 1
                            b += os.path.getsize(os.path.join(dd, f))
                    excl.append({"path": os.path.join(root, rel_d, x), "files": n, "bytes": b, "why": why})
                else:
                    keep.append(x)
            ds[:] = keep
            for f in sorted(fs):
                rel = os.path.join(rel_d, f) if rel_d else f
                src = os.path.join(root, rel)
                size = os.path.getsize(os.path.join(d, f))
                skip = SKIP_FILES.get((label, rel))
                if skip:
                    excl.append({"path": src, "files": 1, "bytes": size, "why": skip})
                elif is_doc(f):
                    plan.append({"source": src, "dest_rel": f"{DRIVE_DIR}\\{label}\\{rel}", "size": size,
                                 "group": f"{label}\\{rel_d.split(chr(92))[0] if rel_d else '(top)'}"})
                else:
                    excl.append({"path": src, "files": 1, "bytes": size, "why": f"not a document ({ext_of(f)})"})
    return plan, excl


def cmd_plan(args):
    plan, excl = select(args.staged, SOURCES if not args.source else
                        [tuple(s.split("=", 1)) for s in args.source])
    for r in plan:
        r["sha256"] = sha256_file(r["source"])
    os.makedirs(args.out, exist_ok=True)
    NP.wcsv(os.path.join(args.out, "records_plan.csv"), PLAN_FIELDS, plan)
    NP.wcsv(os.path.join(args.out, "excluded.csv"), ["path", "files", "bytes", "why"], excl)
    with io.open(os.path.join(args.out, "README_section.txt"), "w", encoding="ascii", newline="") as f:
        f.write(README_SECTION.replace("\n", "\r\n"))
    by = collections.OrderedDict()
    for r in plan:
        e = by.setdefault(r["group"], [0, 0])
        e[0] += 1
        e[1] += int(r["size"])
    print(f"records plan: {len(plan):,} files, {sum(int(r['size']) for r in plan) / 1e9:.2f} GB -> "
          f"{os.path.join(args.records, DRIVE_DIR)}")
    for g, (n, b) in by.items():
        print(f"  {n:6,d} {b / 1e6:10.1f} MB  {g}")
    dup = [k for k, n in collections.Counter(r["dest_rel"].lower() for r in plan).items() if n > 1]
    longest = max(len(os.path.join(args.records, r["dest_rel"])) for r in plan)
    print(f"  longest destination path {longest} characters; duplicate destinations {len(dup)}")
    xb = collections.Counter()
    for x in excl:
        xb[x["why"]] += int(x["bytes"])
    print(f"left out: {sum(int(x['files']) for x in excl):,} files, {sum(xb.values()) / 1e9:.2f} GB")
    for why, b in xb.most_common():
        print(f"  {b / 1e9:9.2f} GB  {why}")
    print(f"written: {args.out}\\records_plan.csv, excluded.csv, README_section.txt")
    return 1 if dup else 0


def read_plan(path):
    with io.open(lp(path), encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def read_records_manifest(path):
    if not os.path.exists(lp(path)):
        return {}
    with io.open(lp(path), encoding="utf-8-sig", newline="") as f:
        return {r["relpath"].lower(): r for r in csv.DictReader(f)}


def copy_one(src, dst, want):
    """Copy src to dst through a temporary name, hashing the source as it is read; -> sha256 of the copy."""
    tmp = dst + ".~records.part"
    os.makedirs(lp(os.path.dirname(dst)), exist_ok=True)
    h = hashlib.sha256()
    with open(lp(src), "rb") as fi, open(lp(tmp), "wb") as fo:
        for b in iter(lambda: fi.read(8 << 20), b""):
            h.update(b)
            fo.write(b)
    if h.hexdigest() != want:
        os.remove(lp(tmp))
        raise SystemExit(f"STOP: the source changed since the plan: {src}")
    try:
        shutil.copystat(lp(src), lp(tmp))   # keep the source's times; not essential on every share
    except OSError:
        pass
    os.replace(lp(tmp), lp(dst))
    return sha256_file(dst)


def cmd_copy(args):
    plan = read_plan(args.plan)
    man_path = os.path.join(args.records, "records_manifest.csv")
    listed = read_records_manifest(man_path)
    todo, same, clash = [], [], []
    for r in plan:
        dst = os.path.join(args.records, r["dest_rel"])
        old = listed.get(r["dest_rel"].lower())
        if old is not None and old["sha256"] != r["sha256"]:
            clash.append(f"{r['dest_rel']}: records_manifest.csv lists other bytes")
        if os.path.exists(lp(dst)):
            if sha256_file(dst) == r["sha256"]:
                same.append(r)
            else:
                clash.append(f"{r['dest_rel']}: the destination holds other bytes")
        else:
            todo.append(r)
    print(f"plan {len(plan):,} files: to copy {len(todo):,} ({sum(int(r['size']) for r in todo) / 1e9:.2f} GB), "
          f"already there and identical {len(same):,}, conflicts {len(clash)}")
    for c in clash[:20]:
        print(f"  CONFLICT {c}")
    if clash:
        print("STOP: nothing copied")
        return 2
    if not args.execute:
        print("dry run: nothing written (add --execute)")
        return 0
    done = 0
    for r in todo:
        got = copy_one(r["source"], os.path.join(args.records, r["dest_rel"]), r["sha256"])
        if got != r["sha256"]:
            raise SystemExit(f"STOP: the copy does not re-hash to the plan: {r['dest_rel']}")
        done += 1
        if done % 500 == 0:
            print(f"  ... {done:,}/{len(todo):,}")
    # records_manifest.csv: append the rows not yet listed; BOM and CRLF as the file has them
    new_rows = [r for r in plan if r["dest_rel"].lower() not in listed]
    exists = os.path.exists(lp(man_path))
    with open(lp(man_path), "ab") as f:
        if not exists:
            f.write("\ufeffrelpath,size,sha256\r\n".encode("utf-8"))
        for r in new_rows:
            buf = io.StringIO()
            csv.writer(buf, lineterminator="\r\n").writerow([r["dest_rel"], r["size"], r["sha256"]])
            f.write(buf.getvalue().encode("utf-8"))
    readme = os.path.join(args.records, "README.txt")
    text = io.open(lp(readme), encoding="utf-8", newline="").read() if os.path.exists(lp(readme)) else ""
    if README_MARK not in text:
        with open(lp(readme), "ab") as f:
            f.write(README_SECTION.replace("\n", "\r\n").encode("ascii"))
    print(f"COPY DONE: {done:,} copied and re-hashed; records_manifest.csv +{len(new_rows):,} rows; README.txt "
          f"{'already had' if README_MARK in text else 'gained'} the drive-3 section")
    return 0


def cmd_verify(args):
    plan = read_plan(args.plan)
    listed = collections.Counter()
    rows = {}
    with io.open(lp(os.path.join(args.records, "records_manifest.csv")), encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            listed[r["relpath"].lower()] += 1
            rows[r["relpath"].lower()] = r
    bad = []
    for r in plan:
        dst = os.path.join(args.records, r["dest_rel"])
        k = r["dest_rel"].lower()
        if not os.path.exists(lp(dst)):
            bad.append(f"missing {r['dest_rel']}")
        elif sha256_file(dst) != r["sha256"]:
            bad.append(f"other bytes {r['dest_rel']}")
        if listed[k] != 1 or rows.get(k, {}).get("sha256") != r["sha256"] or str(rows.get(k, {}).get("size")) != str(r["size"]):
            bad.append(f"records_manifest.csv row {r['dest_rel']}: listed {listed[k]}x")
    readme = os.path.join(args.records, "README.txt")
    has = os.path.exists(lp(readme)) and README_MARK in io.open(lp(readme), encoding="utf-8").read()
    if not has:
        bad.append("README.txt lacks the drive-3 section")
    for b in bad[:20]:
        print(f"  FAIL {b}")
    print(f"{'RECORDS VERIFY PASS' if not bad else 'RECORDS VERIFY FAIL'}: {len(plan):,} files re-hashed; "
          f"{len(bad)} problems")
    return 1 if bad else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--out", required=True)
    p.add_argument("--staged", default=STAGED)
    p.add_argument("--records", default=RECORDS)
    p.add_argument("--source", nargs="*", help="LABEL=PATH pairs instead of the two D: folders (tests)")
    for name in ("copy", "verify"):
        s = sub.add_parser(name)
        s.add_argument("--plan", required=True)
        s.add_argument("--records", default=RECORDS)
        if name == "copy":
            s.add_argument("--execute", action="store_true")
    args = ap.parse_args(argv)
    return {"plan": cmd_plan, "copy": cmd_copy, "verify": cmd_verify}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
