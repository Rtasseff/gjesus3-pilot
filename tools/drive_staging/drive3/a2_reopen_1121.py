#!/usr/bin/env python3
"""a2_reopen_1121.py -- what `tools/reopen_project.py --project AE-biomaGUNE-1121` would do, re-derived
read-only. THE TOOL ITSELF IS NOT RUN (coordinator's instruction).

reopen_project.py's own --dry-run is write-free (every write in it sits behind `if not dry`: the backup,
the skeleton, _project.yaml, the links, the registry lock and row, the index). This script goes one
step further and does not call its main() at all: it imports only the read-only helpers the tool uses
for its decisions and replays step 4 (the links) and step 5 (the registry values) exactly:

  * reopen_project.link_names_from_provenance / closeout_backup_dir / sidecar_discovered (reads);
  * relink_projects.load_registry_index / raw_primary_path / load_link_template (reads);
  * ingest.resolver.resolve_link_filename (pure), ingest.linker.inspect_link_target (documented
    "Read-only: what sits at <project>/raw_linked/<link_name>").

Outputs: a2\\reopen_1121.csv (one row per acquisition: would-be link name, its source, the state) and
a2\\reopen_1121_summary.txt.
"""
import collections
import contextlib
import io
import os
import sys

import a2_common as C

import reopen_project as RP  # noqa: E402  (imported for its helpers; main() is never called)
from ingest import linker, projects_registry, resolver  # noqa: E402
from ingest import project_ids as pids  # noqa: E402

PROJECT = "AE-biomaGUNE-1121"


def main():
    C.stdout_utf8()
    nas = C.NAS
    lines = []

    def say(m):
        lines.append(m)
        print(m, flush=True)

    rows = projects_registry.read_projects(projects_registry.projects_registry_path(nas))
    proj = projects_registry.find_project(rows, PROJECT)
    pid, status = proj["project_id"], proj["status"]
    folder = os.path.join(nas, proj["folder_location"].strip("/").replace("/", os.sep))
    say(f"{pid} {PROJECT} status={status} folder={folder} folder_exists={os.path.isdir(folder)}")
    say(f"registry description: {proj['description']}")
    say(f"registry notes: {proj['notes']}")
    registry = RP.RL.load_registry_index(nas)
    acqs = [r for r in registry.values() if pids.has_project_id(r.get("project_id"), pid)]
    dates = sorted(r["acquisition_datetime"][:10] for r in acqs if len(r["acquisition_datetime"]) >= 10)
    say(f"acquisitions in registry_raw.csv with {pid}: {len(acqs)}; dates {dates[0] if dates else '-'} .. "
        f"{dates[-1] if dates else '-'} ({len(acqs) - len(dates)} without a date)")
    inst = collections.Counter(r.get("instrument", "") for r in acqs)
    say(f"by instrument: {dict(inst)}")
    multi = [r["acq_id"] for r in acqs if ";" in (r.get("project_id") or "")]
    say(f"acquisitions whose project cell names more than one project: {len(multi)}")

    bdir = RP.closeout_backup_dir(pid)
    say(f"close-out backup folder: {bdir}")
    prov_path = os.path.join(folder, "provenance.csv")
    names = RP.link_names_from_provenance([os.path.join(bdir, "provenance.csv") if bdir else None, prov_path])
    say(f"link names recorded in provenance (close-out backup + current): {len(names)}")
    listing = set()
    if bdir and os.path.isfile(os.path.join(bdir, "raw_linked.listing.txt")):
        with io.open(os.path.join(bdir, "raw_linked.listing.txt"), encoding="utf-8", errors="replace") as f:
            for ln in f:
                ln = ln.strip()
                if ln:
                    listing.add(ln)   # whole line: MRI link names contain commas (`..._10_1,3`)
    say(f"entries in the close-out raw_linked listing: {len(listing)}")

    # --- replay of reopen_project.main() step 4, read-only -----------------------------------------
    out = []
    stats = collections.Counter()
    by_source = collections.Counter()
    planned = {}
    order = sorted(acqs, key=lambda r: (r["acq_id"] not in names, r["acq_id"]))
    for r in order:
        aid = r["acq_id"]
        primary = RP.RL.raw_primary_path(nas, r)
        rec = {"acq_id": aid, "instrument": r.get("instrument", ""), "acquisition_datetime": r.get("acquisition_datetime", ""),
               "original_name": r.get("original_name", ""), "canonical_path": r.get("canonical_path", ""),
               "raw_primary_exists": "", "link_name": "", "name_source": "", "state": "", "in_closeout_listing": ""}
        if not os.path.exists(primary):
            stats["no_raw"] += 1
            rec.update(raw_primary_exists="N", state="NO RAW PRIMARY (the tool would STOP)")
            out.append(rec)
            continue
        rec["raw_primary_exists"] = "Y"
        link = names.get(aid)
        src = "provenance"
        if not link:
            tmpl = RP.RL.load_link_template(r.get("ingest_config", ""))
            cfg = dict(r)
            cfg["discovered"] = RP.sidecar_discovered(nas, r)
            link = None
            if tmpl:
                with contextlib.redirect_stdout(io.StringIO()):
                    link = resolver.resolve_link_filename(tmpl, cfg, aid, aid.split("-")[1])
            src = "template"
            if not link or "${" in link:
                link = (r.get("original_name") or "").replace("\\", "/").rstrip("/").split("/")[-1]
                src = "basename"
                if not link or link.isdigit() or len(link) < 4:
                    stats["unnamed"] += 1
                    rec.update(name_source="basename", state="NO SAFE LINK NAME (the tool would STOP)")
                    out.append(rec)
                    continue
        link = link.rstrip("/\\")
        rec["link_name"] = link
        rec["name_source"] = src
        rec["in_closeout_listing"] = "Y" if link in listing else "N"
        if planned.get(link.lower(), aid) != aid:
            stats["collision"] += 1
            rec["state"] = f"COLLISION with {planned[link.lower()]} (same name in this run; reported, not created)"
            out.append(rec)
            continue
        planned[link.lower()] = aid
        state, _dest, detail = linker.inspect_link_target(folder, link, primary)
        if state == linker.LINK_OWN:
            stats["present"] += 1
            rec["state"] = "present"
        elif state == linker.LINK_TAKEN:
            stats["collision"] += 1
            rec["state"] = f"COLLISION: {detail}"
        else:
            stats["created"] += 1
            by_source[src] += 1
            rec["state"] = "would create"
        out.append(rec)
    say(f"replayed step 4 (links): {dict(stats)}; names from {dict(by_source)}")
    stop = stats["no_raw"] or stats["unnamed"]
    say("the tool would " + ("STOP before flipping the status (errors above)" if stop else
                             "go on to step 5 (status -> active) and step 6 (index.html)"))
    say(f"step 5 would set: status active; start_date {dates[0] if dates else proj['start_date']}; "
        f"last_activity {dates[-1] if dates else proj['last_activity']}; notes += 'Reopened <date> (<reason>).'")
    not_listed = sorted(listing - {o['link_name'] for o in out})
    say(f"close-out listing entries with no acquisition in this run: {len(not_listed)}"
        + (f" (e.g. {', '.join(not_listed[:5])})" if not_listed else ""))
    C.wcsv(C.out_path("reopen_1121.csv"), list(out[0].keys()) if out else ["acq_id"], out)
    with open(C.out_path("reopen_1121_summary.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
