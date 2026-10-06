#!/usr/bin/env python3
"""reopen_project.py -- reopen a CLOSED project: status back to active, folder skeleton, the project
links the close-out removed, and its Finder page.

    python tools/reopen_project.py --nas-root "J:\\gjesus3-data" --project AE-biomaGUNE-0219 --dry-run
    python tools/reopen_project.py --nas-root "J:\\gjesus3-data" --project AE-biomaGUNE-0219 --reason "..."

WHY. The 2026-07-14 retention close-out (CHANGELOG) set 8 projects to `closed` and deleted their
folders. Closed projects keep receiving data: the ingest ignores `closed`, so `AE-biomaGUNE-1019`
got 18 AxioScan sections on 2026-09-29 and the historical drives carry more for `0219` and `1019`.
Ryan, 2026-09-30: closed projects are reopened case by case. This is the reusable step.

WHAT IT DOES, in this order (so a failure part-way leaves the project `closed` and a re-run resumes):
  1. refuses a project that is not in registry_projects.csv; a project that is not `closed` is a
     no-op (a re-run after success does nothing);
  2. backs up registry_projects.csv and the project's provenance.csv / _project.yaml to a FRESH dated
     off-NAS directory and verifies the copies by SHA-256;
  3. ensures the folder skeleton (raw_linked/ working/ outputs/ metadata/); writes _project.yaml only
     if it is missing -- from the 2026-07-14 close-out backup when one exists (migrated to the current
     schema: `short_name:` -> `name:`, dates recomputed), else from create_project's template.
     Existing content is never touched;
  4. for every registry_raw row whose project_id includes this project, ensures a hard link exists in
     raw_linked/: a link that already IS the raw primary (same file) is left alone; a missing one is
     created with linker.create_hardlink under its original name (from the project's provenance --
     current, then the close-out backup), else the name its ingest config's link_filename resolves to,
     else the original_name's basename; each created link gets a provenance row. A name already taken
     by a DIFFERENT file, or by a folder holding any file that is not this acquisition's, is a
     collision: reported, never replaced or merged into (linker.inspect_link_target). Nothing is ever deleted;
  5. under the registry lock, through ingest/projects_registry.update_row: status -> active, notes +=
     "Reopened YYYY-MM-DD (<reason>)", start_date / last_activity recomputed from the project's
     acquisition dates (the 2026-07-14 definition; blank dates excluded);
  6. regenerates the project's index.html (generate_index.py --project), which skips closed projects.

On links (05_PROJECTS §3a): researchers may delete links in their folders and nothing recreates
those. The links recreated here were removed by the SYSTEM's close-out, so restoring them is right.

--dry-run writes nothing and prints exactly what would change.
"""
import argparse
import csv
import datetime as dt
import glob
import hashlib
import os
import re
import shutil
import subprocess
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
from ingest import linker, locking, project_ids as pids, project_layout, projects_registry, provenance, resolver, resources  # noqa: E402
import relink_projects as RL  # noqa: E402

CLOSEOUT_BACKUP = r"C:\Users\rtasseff\temp\gjesus3_backfill_backup_20260714\deleted_projects"
BACKUP_ROOT = r"C:\Users\rtasseff\temp"


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def closeout_backup_dir(project_id):
    """The close-out backup folder whose _project.yaml names this project_id (folders there carry
    the pre-2026-08-02 names, e.g. proj-ae-biomegune-0219)."""
    for y in glob.glob(os.path.join(CLOSEOUT_BACKUP, "*", "_project.yaml")):
        with open(y, encoding="utf-8", errors="replace") as f:
            if re.search(rf"^project_id:\s*{re.escape(project_id)}\s*$", f.read(), re.M):
                return os.path.dirname(y)
    return None


def link_names_from_provenance(paths):
    """acq_id -> the LAST hard-link name recorded for it across the given provenance files.

    Only rows that record a link being CREATED (`hardlink` / `hardlink-folder`) count: a
    `hardlink-removed` event (the retire tool; repair_link_collisions prune-foreign, which removes an
    acquisition's merged-in names from ANOTHER acquisition's folder) names a link that is not, or
    is no longer, that acquisition's own."""
    names = {}
    for p in paths:
        if not p or not os.path.isfile(p):
            continue
        with open(p, encoding="utf-8", errors="replace", newline="") as f:
            for r in csv.DictReader(f):
                acq = (r.get("input_refs") or "").strip()
                name = (r.get("output_name") or "").strip()
                if acq.startswith("ACQ-") and name and not name.lower().endswith(".lnk") \
                        and (r.get("file_type") or "") in ("hardlink", "hardlink-folder"):
                    names[acq] = name
    return names


def sidecar_discovered(nas, row):
    """The acquisition's own discovered.* block (link templates reference it)."""
    import json
    p = os.path.join(nas, row["canonical_path"].strip("/").replace("/", os.sep), "metadata.json")
    try:
        with open(p, encoding="utf-8") as f:
            return (json.load(f).get("discovered") or {})
    except (OSError, ValueError):
        return {}


def is_same(link, primary):
    """True if `link` is the raw primary: same file, or (folder primary) a folder whose every file
    is the same file as the primary's."""
    if os.path.isdir(primary):
        if not os.path.isdir(link):
            return False
        for root, _d, files in os.walk(primary):
            for fn in files:
                rel = os.path.relpath(os.path.join(root, fn), primary)
                other = os.path.join(link, rel)
                if not os.path.isfile(other) or not os.path.samefile(other, os.path.join(root, fn)):
                    return False
        return True
    return os.path.isfile(link) and os.path.samefile(link, primary)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--nas-root", required=True)
    ap.add_argument("--project", required=True, help="project name or PROJ-XXXX")
    ap.add_argument("--reason", default="new data for a closed project")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8", errors="replace")
    nas = os.path.normpath(args.nas_root)
    dry = args.dry_run
    today = dt.date.today().isoformat()
    reg_dir = os.path.join(nas, "registries")
    proj_csv = projects_registry.projects_registry_path(nas)
    tag = "[dry-run] " if dry else ""

    rows = projects_registry.read_projects(proj_csv)
    proj = projects_registry.find_project(rows, args.project)
    if not proj:
        print(f"REFUSED: {args.project} is not in {proj_csv}")
        return 2
    pid, name, status = proj["project_id"], proj["name"], (proj["status"] or "").strip()
    folder = os.path.join(nas, proj["folder_location"].strip("/").replace("/", os.sep))
    print(f"{tag}{pid} {name} status={status} folder={folder}")
    if status != "closed":
        print(f"no-op: {name} is '{status}', not closed")
        return 0

    registry = RL.load_registry_index(nas)
    acqs = [r for r in registry.values() if pids.has_project_id(r.get("project_id"), pid)]
    dates = sorted(r["acquisition_datetime"][:10] for r in acqs if len(r["acquisition_datetime"]) >= 10)
    start, last = (dates[0], dates[-1]) if dates else (proj["start_date"], proj["last_activity"])
    print(f"{tag}{len(acqs)} acquisitions in production; acquisition dates {start} .. {last} "
          f"({len(acqs) - len(dates)} without a date, excluded)")

    # --- 2. backup -------------------------------------------------------------------------------
    prov_path = os.path.join(folder, "provenance.csv")
    yaml_path = os.path.join(folder, "_project.yaml")
    if not dry:
        bk = os.path.join(BACKUP_ROOT, f"gjesus3_reopen_backup_{dt.datetime.now():%Y%m%d_%H%M%S}_{name}")
        if os.path.exists(bk):
            print(f"STOP: backup dir {bk} exists")
            return 3
        os.makedirs(bk)
        for src in (proj_csv, prov_path, yaml_path):
            if os.path.isfile(src):
                dst = os.path.join(bk, os.path.basename(src))
                shutil.copy2(src, dst)
                if sha256(src) != sha256(dst):
                    print(f"STOP: backup of {src} does not verify")
                    return 3
        print(f"backup: {bk} (verified)")

    # --- 3. skeleton + _project.yaml ----------------------------------------------------------------
    missing = project_layout.missing_subfolders(folder) if os.path.isdir(folder) else list(project_layout.SUBFOLDER_NAMES)
    print(f"{tag}skeleton: create {missing or 'nothing'}")
    bdir = closeout_backup_dir(pid)
    if not os.path.isfile(yaml_path):
        if bdir:
            raw = open(os.path.join(bdir, "_project.yaml"), "rb").read()
            try:
                content = raw.decode("utf-8")
            except UnicodeDecodeError:       # some close-out backups were written as cp1252
                content = raw.decode("cp1252")
            content = re.sub(r"^short_name:.*$", f"name: {name}", content, flags=re.M)
            src_note = f"the 2026-07-14 close-out backup ({os.path.basename(bdir)}), migrated to the current schema"
        else:
            with open(resources.resource_path("templates", "project.yaml"), encoding="utf-8") as f:
                content = f.read()
            for k, v in {"{project_id}": pid, "{name}": name, "{description}": proj["description"],
                         "{owner}": proj["owner"], "{start_date}": start}.items():
                content = content.replace(k, v)
            src_note = "create_project's template"
        content = re.sub(r"^start_date:.*$", f"start_date: {start}", content, flags=re.M)
        content = re.sub(r"^last_activity:.*$", f"last_activity: {last}", content, flags=re.M)
        content = content.rstrip("\n") + f"\n  Reopened {today} ({args.reason}) by reopen_project.py.\n"
        print(f"{tag}_project.yaml: write from {src_note}")
    else:
        content = None
        print(f"{tag}_project.yaml: present, left as it is")
    if not dry:
        os.makedirs(folder, exist_ok=True)
        project_layout.ensure_subfolders(folder)
        if content is not None:
            tmp = yaml_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp, yaml_path)
        if not os.path.isfile(prov_path):
            provenance.write_empty(prov_path)

    # --- 4. links ------------------------------------------------------------------------------------------
    names = link_names_from_provenance([os.path.join(bdir, "provenance.csv") if bdir else None, prov_path])
    raw_linked = os.path.join(folder, "raw_linked")
    stats = {"present": 0, "created": 0, "collision": 0, "no_raw": 0, "error": 0}
    by_source = {"provenance": 0, "template": 0, "basename": 0}
    planned = {}   # link name (lower-case: Windows) -> the acq it is planned for, in THIS run
    # provenance names first, so a name an acquisition really carried wins over a template's
    order = sorted(acqs, key=lambda r: (r["acq_id"] not in names, r["acq_id"]))
    for r in order:
        aid = r["acq_id"]
        primary = RL.raw_primary_path(nas, r)
        if not os.path.exists(primary):
            stats["no_raw"] += 1
            print(f"  NO RAW PRIMARY {aid}: {primary}")
            continue
        link = names.get(aid)
        src = "provenance"
        if not link:
            tmpl = RL.load_link_template(r.get("ingest_config", ""))
            cfg = dict(r)
            cfg["discovered"] = sidecar_discovered(nas, r)   # templates use ${discovered.*}
            link = None
            if tmpl:
                import contextlib, io
                with contextlib.redirect_stdout(io.StringIO()):
                    link = resolver.resolve_link_filename(tmpl, cfg, aid, aid.split("-")[1])
            src = "template"
            if not link or "${" in link:
                link = (r.get("original_name") or "").replace("\\", "/").rstrip("/").split("/")[-1]
                src = "basename"
                if not link or link.isdigit() or len(link) < 4:
                    stats["unnamed"] = stats.get("unnamed", 0) + 1
                    print(f"  NO SAFE LINK NAME {aid}: template unresolved, basename {link!r} -- skipped")
                    continue
        link = link.rstrip("/\\")
        if planned.get(link.lower(), aid) != aid:
            stats["collision"] += 1
            print(f"  COLLISION {aid}: its link name {link!r} belongs to {planned[link.lower()]} "
                  f"(same link template, e.g. two sessions of one animal on one day) -- not created")
            continue
        planned[link.lower()] = aid
        # linker.inspect_link_target (2026-10-05): complete -> present; a folder holding only some of
        # this acquisition's own files -> completed additively; anything else (another acquisition's
        # files, even mixed with this one's) -> a collision, never merged into.
        state, _dest, detail = linker.inspect_link_target(folder, link, primary)
        if state == linker.LINK_OWN:
            stats["present"] += 1
            continue
        if state == linker.LINK_TAKEN:
            stats["collision"] += 1
            print(f"  COLLISION {aid}: raw_linked/{link} exists and is NOT this acquisition ({detail}) -- left alone")
            continue
        by_source[src] += 1
        if dry:
            stats["created"] += 1
            if stats["created"] <= 5:
                print(f"  {tag}link {aid} -> raw_linked/{link}  (name from {src})")
            continue
        try:
            out = linker.create_hardlink(folder, link, primary)
            if not is_same(out, primary):
                raise RuntimeError("link is not the raw primary after creation")
            is_dir = os.path.isdir(out)
            provenance.append_entry(prov_path, {
                "output_path": f"raw_linked/{link}", "output_name": link,
                "file_type": "hardlink-folder" if is_dir else "hardlink",
                "date_created": today, "creator": r.get("operator", "") or "",
                "input_refs": aid,
                "process_description": "Recreated by reopen_project.py: the link was removed by the "
                                       "2026-07-14 retention close-out (system, not researcher)",
                "software_version": provenance.software_version_string("reopen_project.py"),
                "parameters_ref": r.get("ingest_config", "") or "", "lab_notebook_ref": "",
                "notes": f"Project reopened {today} ({args.reason})",
            })
            stats["created"] += 1
        except linker.LinkCollisionError as ex:   # taken since the check above: reported, left alone
            stats["collision"] += 1
            print(f"  COLLISION {aid}: {ex} -- left alone")
        except Exception as ex:  # noqa: BLE001 -- counted; the status is not flipped on errors
            stats["error"] += 1
            print(f"  ERROR {aid}: {type(ex).__name__}: {ex}")
    print(f"{tag}links: {stats}; names from {by_source}")
    if stats["error"] or stats["no_raw"] or stats.get("unnamed"):
        print("STOP: errors while linking -- the project stays closed; fix and re-run")
        return 4

    # --- 5. registry row -----------------------------------------------------------------------------------
    notes = (proj["notes"] or "").rstrip()
    upd = {"status": "active", "start_date": start, "last_activity": last,
           "notes": (notes + " " if notes else "") + f"Reopened {today} ({args.reason})."}
    for k, v in upd.items():
        if (proj.get(k) or "") != v:
            print(f"{tag}registry_projects {pid}.{k}: {proj.get(k)!r} -> {v!r}")
    if not dry:
        with locking.registry_lock(reg_dir):
            found, applied = projects_registry.update_row(
                proj_csv, pid, upd, allowed=["status", "start_date", "last_activity", "notes"])
        if not found:
            print("STOP: the project row vanished during the run")
            return 5
        print(f"registry_projects: updated {sorted(applied)}")

    # --- 6. Finder page ---------------------------------------------------------------------------------
    cmd = [sys.executable, os.path.join(TOOLS, "generate_index.py"), "--nas-root", nas, "--project", pid]
    if dry:
        print(f"{tag}would run: {' '.join(cmd)}")
    else:
        rc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        print(f"index: rc={rc.returncode} {rc.stdout.strip().splitlines()[-1:] if rc.stdout else ''}")
    print("Note: the links recreated here were removed by the system's 2026-07-14 close-out, not by a "
          "researcher (05_PROJECTS §3a), so restoring them is correct.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
