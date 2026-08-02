#!/usr/bin/env python3
"""migrate_project_naming.py — one-shot live migration to the project reference
model (05_PROJECTS §2a, DECIDED 2026-08-02).

WHAT IT CHANGES ON THE NAS

  a. registry_raw.csv    HEADER ONLY: `project_hint` -> `project_id`.
                         The 13,582 row VALUES are already resolved PROJ-ids —
                         verified — so there is nothing to rewrite. The header
                         line is swapped byte-for-byte and every data byte is
                         copied through untouched.
  b. registry_projects.csv  header `short_name` -> `name`; per row the new name
                         (drop `proj-`, restore casing, fix the biomeGUNE typo)
                         and `folder_location` = /projects/<name>/.
  c. projects/<old>      renamed to projects/<name>. Hard links are untouched by
                         a parent rename — the /raw inodes never move.
  d. <project>/_project.yaml   key `short_name:` -> `name:` with the new value.
  e. recipes/*.yaml      DELETED (they carry the retired `registry.project_hint`
                         key and would now fail loudly). Backed up first;
                         operators recreate them in the builder.

  /raw/ is NEVER touched. Sidecars carry no project reference; provenance
  `output_path` is relative (`raw_linked/<link>`) — verified, rename-safe.

USAGE

    # 1. look at the plan (default; changes nothing)
    python tools/migrate_project_naming.py --nas-root J:\\gjesus3-data

    # 2. apply it, in a no-ingest window
    python tools/migrate_project_naming.py --nas-root J:\\gjesus3-data --apply

    # 3. check afterwards (also run automatically at the end of --apply)
    python tools/migrate_project_naming.py --nas-root J:\\gjesus3-data --verify

    # 4. put everything back, if verification fails
    python tools/migrate_project_naming.py --nas-root J:\\gjesus3-data \\
        --reverse --from-backup C:\\Users\\rtasseff\\temp\\gjesus3_projectnaming_backup_YYYYMMDD

RESUMABLE. Every step tests the live state first and skips what is already
done, so a re-run after an interruption completes the remainder rather than
double-applying. Registry writes are temp+os.replace under the registries
lock. Run `--apply` only with no ingest in flight.
"""

import argparse
import csv
import io
import json
import os
import re
import shutil
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ingest import locking  # noqa: E402
from ingest import project_naming  # noqa: E402

# Animal-protocol projects: `[ae-]biom{a,e}gune-NNNN` in any casing becomes the
# one canonical spelling. The `a` matches the animal facility's own facility_ids
# (716/716 subject rows); `biomeGUNE` was a recipe typo.
_AE_RE = re.compile(r"^ae-?biom[ae]gune-(?P<code>.+)$", re.IGNORECASE)
CANONICAL_AE = "AE-biomaGUNE"

OLD_RAW_COL, NEW_RAW_COL = "project_hint", "project_id"
OLD_PROJ_COL, NEW_PROJ_COL = "short_name", "name"


def log(msg, level="INFO"):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {level}: {msg}")


# ---------------------------------------------------------------- mapping

def new_name_for(old_short_name):
    """The project's new name: drop nothing but the folder's `proj-` prefix,
    and fold the animal-protocol projects onto the canonical spelling.

    `ae-biomegune-0525` -> `AE-biomaGUNE-0525`   (casing restored, typo fixed)
    `laura-tholt`       -> `laura-tholt`          (person/topic slug unchanged)
    """
    s = (old_short_name or "").strip()
    m = _AE_RE.match(s)
    if m:
        return f"{CANONICAL_AE}-{m.group('code')}"
    return s


def read_projects(path):
    """Rows of registry_projects.csv, plus the header list, BOM-tolerantly."""
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def build_mapping(nas_root):
    """The old->new plan, derived from the LIVE registry — never hardcoded.

    Returns (rows, problems) where each row is a dict describing one project.
    """
    reg = os.path.join(nas_root, "registries", "registry_projects.csv")
    header, rows = read_projects(reg)
    name_col = NEW_PROJ_COL if NEW_PROJ_COL in header else OLD_PROJ_COL
    projects_dir = os.path.join(nas_root, "projects")
    on_disk = {d.lower(): d for d in os.listdir(projects_dir)
               if os.path.isdir(os.path.join(projects_dir, d))}

    plan, problems = [], []
    seen = {}
    for r in rows:
        pid = (r.get("project_id") or "").strip()
        old_name = (r.get(name_col) or "").strip()
        old_loc = (r.get("folder_location") or "").strip()
        old_folder = old_loc.strip("/").split("/")[-1] if old_loc else ""
        new_name = new_name_for(old_name)

        if not new_name:
            problems.append(f"{pid}: empty project name — cannot derive a folder")
            continue
        errs = project_naming.validate_project_name(new_name)
        if errs:
            problems.append(f"{pid}: new name {new_name!r} is not usable: {errs}")
        dup = seen.get(new_name.lower())
        if dup:
            problems.append(
                f"{pid}: new name {new_name!r} collides with {dup} "
                f"(names must be unique case-insensitively)")
        seen[new_name.lower()] = pid

        present = old_folder.lower() in on_disk
        plan.append({
            "project_id": pid,
            "status": (r.get("status") or "").strip(),
            "old_name": old_name,
            "new_name": new_name,
            "old_folder": on_disk.get(old_folder.lower(), old_folder),
            "new_folder": project_naming.folder_name(new_name),
            "old_location": old_loc,
            "new_location": project_naming.folder_location(new_name),
            "on_disk": present,
        })

    # A folder on disk with no registry row would be silently left behind.
    claimed = {p["old_folder"].lower() for p in plan}
    for low, actual in sorted(on_disk.items()):
        if low not in claimed:
            problems.append(f"folder {actual!r} has no registry row — not migrated")
    return plan, problems


def print_plan(plan, problems):
    renames = [p for p in plan if p["on_disk"]]
    records = [p for p in plan if not p["on_disk"]]
    changed = [p for p in plan if p["old_name"] != p["new_name"]]
    print()
    print("=" * 78)
    print("MIGRATION PLAN — review before --apply")
    print("=" * 78)
    print(f"{'PROJ-ID':<11} {'STATUS':<7} {'OLD FOLDER':<44} NEW FOLDER")
    print("-" * 78)
    for p in plan:
        mark = " " if p["on_disk"] else "*"
        print(f"{p['project_id']:<11} {p['status']:<7} "
              f"{mark}{p['old_folder']:<43} {p['new_folder']}")
    print("-" * 78)
    print(f"  {len(plan):>3} registry rows")
    print(f"  {len(renames):>3} folders renamed on disk")
    print(f"  {len(records):>3} record-only (* = folder absent; closed at close-out)")
    print(f"  {len(changed):>3} names change spelling/casing")
    if problems:
        print()
        print("PROBLEMS — resolve these before applying:")
        for p in problems:
            print(f"  ! {p}")
    print()


# ---------------------------------------------------------------- backup

def make_backup(nas_root, backup_dir, plan):
    """Copy every file this migration can modify, off-NAS, before touching it.

    NEVER overwrites an existing backup. The script is resumable, so a re-run
    after a partial failure would otherwise back up the HALF-MIGRATED state
    over the only copy of the original — silently destroying the rollback at
    exactly the moment it is needed. An existing backup is kept as-is.
    """
    marker = os.path.join(backup_dir, "mapping.json")
    if os.path.isfile(marker):
        log(f"backup already exists at {backup_dir} — KEEPING IT (a re-run must "
            f"not overwrite the pre-migration copy)", "WARN")
        return
    os.makedirs(backup_dir, exist_ok=True)
    regs = os.path.join(nas_root, "registries")
    for fn in ("registry_raw.csv", "registry_projects.csv"):
        src = os.path.join(regs, fn)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(backup_dir, fn))
            log(f"backed up {fn} ({os.path.getsize(src):,} bytes)")

    yml_dir = os.path.join(backup_dir, "_project_yaml")
    os.makedirs(yml_dir, exist_ok=True)
    n = 0
    for p in plan:
        src = os.path.join(nas_root, "projects", p["old_folder"], "_project.yaml")
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(yml_dir, f"{p['project_id']}_project.yaml"))
            n += 1
    log(f"backed up {n} _project.yaml files")

    rec_src = os.path.join(nas_root, "recipes")
    rec_dst = os.path.join(backup_dir, "recipes")
    if os.path.isdir(rec_src):
        os.makedirs(rec_dst, exist_ok=True)
        recs = [f for f in os.listdir(rec_src) if f.lower().endswith((".yaml", ".yml"))]
        for f in recs:
            shutil.copy2(os.path.join(rec_src, f), os.path.join(rec_dst, f))
        log(f"backed up {len(recs)} NAS recipe(s)")

    listing = sorted(os.listdir(os.path.join(nas_root, "projects")))
    with open(os.path.join(backup_dir, "projects_listing_before.txt"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(listing) + "\n")
    with open(os.path.join(backup_dir, "mapping.json"), "w", encoding="utf-8") as f:
        json.dump(plan, f, indent=2, ensure_ascii=False)
    log(f"backup complete: {backup_dir}")


# ---------------------------------------------------------------- steps

def step_raw_header(nas_root, apply):
    """(a) Swap ONE word in the header line; copy every data byte through.

    Rewriting 13,582 rows through the csv module would risk re-quoting or
    re-encoding a value. Reading the header line and streaming the remainder as
    opaque bytes cannot: the data is bit-identical by construction.
    """
    path = os.path.join(nas_root, "registries", "registry_raw.csv")
    with open(path, "rb") as f:
        header = f.readline()
    if NEW_RAW_COL.encode() in header and OLD_RAW_COL.encode() not in header:
        log("(a) registry_raw header already migrated — skipping")
        return True
    if header.count(OLD_RAW_COL.encode()) != 1:
        log(f"(a) expected exactly one '{OLD_RAW_COL}' in the header, "
            f"found {header.count(OLD_RAW_COL.encode())} — refusing", "ERROR")
        return False
    new_header = header.replace(OLD_RAW_COL.encode(), NEW_RAW_COL.encode())
    if not apply:
        log(f"(a) [dry-run] would rewrite the registry_raw header "
            f"({OLD_RAW_COL} -> {NEW_RAW_COL}); values untouched")
        return True
    tmp = path + ".migrating.tmp"
    with open(path, "rb") as src, open(tmp, "wb") as dst:
        src.readline()                      # drop the old header
        dst.write(new_header)
        shutil.copyfileobj(src, dst)        # every data byte, verbatim
    os.replace(tmp, path)
    log(f"(a) registry_raw header migrated: {OLD_RAW_COL} -> {NEW_RAW_COL}")
    return True


def step_projects_registry(nas_root, plan, apply):
    """(b) Header short_name -> name, plus the new name/folder_location per row."""
    path = os.path.join(nas_root, "registries", "registry_projects.csv")
    header, rows = read_projects(path)
    if NEW_PROJ_COL in header and OLD_PROJ_COL not in header:
        done = all((r.get("folder_location") or "").strip()
                   == next((p["new_location"] for p in plan
                            if p["project_id"] == (r.get("project_id") or "").strip()),
                           r.get("folder_location"))
                   for r in rows)
        if done:
            log("(b) registry_projects already migrated — skipping")
            return True
    by_id = {p["project_id"]: p for p in plan}
    new_header = [NEW_PROJ_COL if h == OLD_PROJ_COL else h for h in header]
    name_col = NEW_PROJ_COL if NEW_PROJ_COL in header else OLD_PROJ_COL
    out = []
    for r in rows:
        pid = (r.get("project_id") or "").strip()
        p = by_id.get(pid)
        row = {NEW_PROJ_COL if k == OLD_PROJ_COL else k: v for k, v in r.items()}
        if p:
            row[NEW_PROJ_COL] = p["new_name"]
            row["folder_location"] = p["new_location"]
        else:
            row[NEW_PROJ_COL] = r.get(name_col, "")
        out.append(row)
    if not apply:
        log(f"(b) [dry-run] would rewrite registry_projects: header "
            f"{OLD_PROJ_COL} -> {NEW_PROJ_COL}, {len(out)} rows re-pointed")
        return True
    tmp = path + ".migrating.tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=new_header)
        w.writeheader()
        for row in out:
            w.writerow({k: row.get(k, "") for k in new_header})
    os.replace(tmp, path)
    log(f"(b) registry_projects migrated ({len(out)} rows)")
    return True


def step_folders(nas_root, plan, apply):
    """(c) Rename the project folders. Hard links inside are unaffected."""
    projects = os.path.join(nas_root, "projects")
    renamed = skipped = 0
    for p in plan:
        if not p["on_disk"]:
            continue
        src = os.path.join(projects, p["old_folder"])
        dst = os.path.join(projects, p["new_folder"])
        if p["old_folder"] == p["new_folder"]:
            skipped += 1
            continue
        if not os.path.isdir(src):
            if os.path.isdir(dst):
                skipped += 1          # already renamed on an earlier run
                continue
            log(f"(c) source folder missing: {p['old_folder']}", "WARN")
            continue
        # Case-only differences are the same path on this FS; a genuine
        # collision is a different project and must never be overwritten.
        if os.path.isdir(dst) and os.path.normcase(src) != os.path.normcase(dst):
            log(f"(c) target already exists, refusing: {p['new_folder']}", "ERROR")
            return False
        if not apply:
            renamed += 1
            continue
        os.rename(src, dst)
        renamed += 1
    log(f"(c) {'[dry-run] would rename' if not apply else 'renamed'} "
        f"{renamed} folder(s); {skipped} already correct")
    return True


def step_project_yaml(nas_root, plan, apply):
    """(d) `short_name: <old>` -> `name: <new>`, editing that ONE line.

    The 43 live files are a mix of utf-8 and cp1252 (auto-created descriptions
    carry accented text), so the file is edited as BYTES: only the key line is
    replaced and every other byte is preserved. A decode/re-encode round trip
    would mangle the cp1252 ones.
    """
    changed = missing = 0
    for p in plan:
        folder = p["new_folder"] if apply else p["old_folder"]
        path = os.path.join(nas_root, "projects", folder, "_project.yaml")
        if not os.path.isfile(path):
            alt = os.path.join(nas_root, "projects", p["old_folder"], "_project.yaml")
            path = alt if os.path.isfile(alt) else None
        if not path:
            missing += 1          # the 5 closed-but-present folders have none
            continue
        with open(path, "rb") as f:
            lines = f.readlines()
        new_line = f"{NEW_PROJ_COL}: {p['new_name']}".encode("utf-8")
        hit = False
        for i, ln in enumerate(lines):
            if ln.startswith(OLD_PROJ_COL.encode() + b":") or \
                    ln.startswith(NEW_PROJ_COL.encode() + b":"):
                eol = b"\r\n" if ln.endswith(b"\r\n") else b"\n" if ln.endswith(b"\n") else b""
                if ln == new_line + eol:
                    hit = True
                    break
                lines[i] = new_line + eol
                hit = True
                changed += 1
                break
        if not hit:
            log(f"(d) no name/short_name line in {folder}/_project.yaml", "WARN")
            continue
        if not apply:
            continue
        tmp = path + ".migrating.tmp"
        with open(tmp, "wb") as f:
            f.writelines(lines)
        os.replace(tmp, path)
    log(f"(d) {'[dry-run] would update' if not apply else 'updated'} "
        f"{changed} _project.yaml file(s); {missing} folder(s) have none "
        f"(closed projects — expected)")
    return True


def step_delete_recipes(nas_root, apply):
    """(e) Delete the saved NAS recipes — they carry the retired input key.

    DECIDED: not migrated. A recipe that errors on load is worse than a recipe
    an operator rebuilds in the builder in a minute. Backed up in step 2.
    """
    rec = os.path.join(nas_root, "recipes")
    if not os.path.isdir(rec):
        log("(e) no recipes/ directory — nothing to delete")
        return True
    files = [f for f in os.listdir(rec) if f.lower().endswith((".yaml", ".yml"))]
    if not files:
        log("(e) recipes already cleared — skipping")
        return True
    if not apply:
        log(f"(e) [dry-run] would DELETE {len(files)} recipe(s): {', '.join(sorted(files))}")
        return True
    for f in files:
        os.remove(os.path.join(rec, f))
    log(f"(e) deleted {len(files)} NAS recipe(s) (backed up)")
    return True


# ---------------------------------------------------------------- verify

def verify(nas_root):
    """Post-migration checks. Returns the number of failures."""
    fails = []

    def ck(cond, msg):
        print(f"  {'ok:  ' if cond else 'FAIL:'} {msg}")
        if not cond:
            fails.append(msg)

    regs = os.path.join(nas_root, "registries")
    print("\nVERIFICATION")
    print("-" * 60)

    with open(os.path.join(regs, "registry_raw.csv"), "rb") as f:
        header = f.readline().decode("utf-8", "replace").strip()
    cols = header.split(",")
    ck(NEW_RAW_COL in cols, f"registry_raw has a `{NEW_RAW_COL}` column")
    ck(OLD_RAW_COL not in cols, f"registry_raw has no `{OLD_RAW_COL}` column")

    header_p, rows = read_projects(os.path.join(regs, "registry_projects.csv"))
    ck(NEW_PROJ_COL in header_p, f"registry_projects has a `{NEW_PROJ_COL}` column")
    ck(OLD_PROJ_COL not in header_p, f"registry_projects has no `{OLD_PROJ_COL}` column")

    bad_loc = [r["project_id"] for r in rows
               if (r.get("folder_location") or "").strip()
               != project_naming.folder_location((r.get(NEW_PROJ_COL) or "").strip())]
    ck(not bad_loc, f"every folder_location == /projects/<name>/ "
                    f"({len(bad_loc)} mismatched)")

    projects_dir = os.path.join(nas_root, "projects")
    on_disk = {d for d in os.listdir(projects_dir)
               if os.path.isdir(os.path.join(projects_dir, d))}
    stale = sorted(d for d in on_disk if d.lower().startswith("proj-"))
    ck(not stale, f"no `proj-*` folders remain ({len(stale)}: {stale[:3]})")

    active_missing = [r[NEW_PROJ_COL] for r in rows
                      if (r.get("status") or "").strip().lower() == "active"
                      and r[NEW_PROJ_COL] not in on_disk]
    ck(not active_missing,
       f"every active project's folder exists under its new name "
       f"({len(active_missing)} missing)")

    # The raw->projects join must still resolve for every row.
    ids = {(r.get("project_id") or "").strip() for r in rows}
    unresolved, total = set(), 0
    with open(os.path.join(regs, "registry_raw.csv"), "r",
              encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            total += 1
            v = (row.get(NEW_RAW_COL) or "").strip()
            if v and v not in ids:
                unresolved.add(v)
    ck(not unresolved,
       f"all {total:,} registry_raw rows join to a project "
       f"({len(unresolved)} unresolved: {sorted(unresolved)[:3]})")

    yaml_bad = []
    for r in rows:
        d = os.path.join(projects_dir, r[NEW_PROJ_COL], "_project.yaml")
        if not os.path.isfile(d):
            continue
        with open(d, "rb") as f:
            head = f.read(4096)
        if (NEW_PROJ_COL + ": " + r[NEW_PROJ_COL]).encode("utf-8") not in head:
            yaml_bad.append(r["project_id"])
    ck(not yaml_bad, f"_project.yaml carries `name: <new name>` "
                     f"({len(yaml_bad)} wrong: {yaml_bad[:3]})")

    rec = os.path.join(nas_root, "recipes")
    left = ([f for f in os.listdir(rec) if f.lower().endswith((".yaml", ".yml"))]
            if os.path.isdir(rec) else [])
    ck(not left, f"NAS recipes cleared ({len(left)} left)")

    # Hard links: a spot-check that the project copy is still the same inode as
    # /raw. A folder rename cannot break this, so a failure means something else
    # moved the data.
    checked = same = 0
    for r in rows[:60]:
        rl = os.path.join(projects_dir, r[NEW_PROJ_COL], "raw_linked")
        if not os.path.isdir(rl):
            continue
        for entry in sorted(os.listdir(rl))[:1]:
            path = os.path.join(rl, entry)
            if os.path.isfile(path):
                checked += 1
                if os.stat(path).st_nlink > 1:
                    same += 1
    ck(checked == 0 or same == checked,
       f"hard links intact — {same}/{checked} spot-checked link(s) still "
       f"share their inode with /raw")

    print("-" * 60)
    print(f"{'ALL CHECKS PASSED' if not fails else str(len(fails)) + ' CHECK(S) FAILED'}\n")
    return len(fails)


# ---------------------------------------------------------------- reverse

def reverse(nas_root, backup_dir):
    """Undo: folder names back, then both CSVs and the _project.yaml files
    restored byte-for-byte from the backup. Recipes are restored too."""
    with open(os.path.join(backup_dir, "mapping.json"), encoding="utf-8") as f:
        plan = json.load(f)
    projects = os.path.join(nas_root, "projects")
    n = 0
    for p in plan:
        src = os.path.join(projects, p["new_folder"])
        dst = os.path.join(projects, p["old_folder"])
        if os.path.isdir(src) and not os.path.isdir(dst) and p["on_disk"]:
            os.rename(src, dst)
            n += 1
    log(f"restored {n} folder name(s)")

    regs = os.path.join(nas_root, "registries")
    for fn in ("registry_raw.csv", "registry_projects.csv"):
        b = os.path.join(backup_dir, fn)
        if os.path.isfile(b):
            shutil.copy2(b, os.path.join(regs, fn))
            log(f"restored {fn}")

    yml_dir = os.path.join(backup_dir, "_project_yaml")
    if os.path.isdir(yml_dir):
        n = 0
        for p in plan:
            b = os.path.join(yml_dir, f"{p['project_id']}_project.yaml")
            d = os.path.join(projects, p["old_folder"], "_project.yaml")
            if os.path.isfile(b) and os.path.isdir(os.path.dirname(d)):
                shutil.copy2(b, d)
                n += 1
        log(f"restored {n} _project.yaml file(s)")

    rec_b = os.path.join(backup_dir, "recipes")
    if os.path.isdir(rec_b):
        rec = os.path.join(nas_root, "recipes")
        os.makedirs(rec, exist_ok=True)
        for f in os.listdir(rec_b):
            shutil.copy2(os.path.join(rec_b, f), os.path.join(rec, f))
        log(f"restored {len(os.listdir(rec_b))} recipe(s)")
    log("REVERSE COMPLETE — re-run the old code against this state.")


# ---------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Migrate the live NAS to the project reference model "
                    "(05_PROJECTS §2a). Dry-run by default.")
    ap.add_argument("--nas-root", default=os.environ.get("GJESUS3_ROOT", "/mnt/gjesus3"),
                    help="NAS root (default: $GJESUS3_ROOT)")
    ap.add_argument("--apply", action="store_true",
                    help="actually make the changes (default is a dry run)")
    ap.add_argument("--verify", action="store_true",
                    help="run only the post-migration checks")
    ap.add_argument("--reverse", action="store_true",
                    help="roll back, using --from-backup")
    ap.add_argument("--from-backup", help="backup directory created by --apply")
    ap.add_argument("--backup-dir",
                    help="where to write the pre-migration backup "
                         "(default: %%TEMP%%/gjesus3_projectnaming_backup_<date>)")
    args = ap.parse_args(argv)

    nas = os.path.normpath(args.nas_root)
    if not os.path.isdir(os.path.join(nas, "registries")):
        log(f"no registries/ under {nas} — is --nas-root right?", "ERROR")
        return 2

    if args.verify:
        return 1 if verify(nas) else 0

    if args.reverse:
        if not args.from_backup or not os.path.isdir(args.from_backup):
            log("--reverse needs --from-backup <dir>", "ERROR")
            return 2
        reverse(nas, args.from_backup)
        return 0

    log(f"NAS root: {nas}")
    plan, problems = build_mapping(nas)
    print_plan(plan, problems)
    if problems:
        log("refusing to continue while the plan has problems", "ERROR")
        return 1

    if not args.apply:
        log("DRY RUN — nothing will be changed. Re-run with --apply to execute.")
        for fn in (lambda: step_raw_header(nas, False),
                   lambda: step_projects_registry(nas, plan, False),
                   lambda: step_folders(nas, plan, False),
                   lambda: step_project_yaml(nas, plan, False),
                   lambda: step_delete_recipes(nas, False)):
            if not fn():
                return 1
        print()
        log("Dry run complete. Review the table above, then --apply.")
        return 0

    backup_dir = args.backup_dir or os.path.join(
        os.environ.get("TEMP", "/tmp"),
        f"gjesus3_projectnaming_backup_{datetime.now().strftime('%Y%m%d')}")
    log(f"APPLYING — backup: {backup_dir}")
    make_backup(nas, backup_dir, plan)

    regs = os.path.join(nas, "registries")
    with locking.registry_lock(regs):
        if not step_raw_header(nas, True):
            return 1
        if not step_projects_registry(nas, plan, True):
            return 1
    if not step_folders(nas, plan, True):
        return 1
    if not step_project_yaml(nas, plan, True):
        return 1
    if not step_delete_recipes(nas, True):
        return 1

    failures = verify(nas)
    if failures:
        log(f"{failures} verification failure(s). The backup is at {backup_dir}; "
            f"roll back with --reverse --from-backup", "ERROR")
        return 1
    log("MIGRATION COMPLETE. Keep the backup until the production smoke test passes.")
    log("Next: regenerate the Finder — "
        "python tools/generate_index.py --nas-root <nas> --per-project")
    return 0


if __name__ == "__main__":
    sys.exit(main())
