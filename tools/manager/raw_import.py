"""Add existing `/raw/` acquisitions to a project — the "import from raw" engine.

This is the *"Select-in-Finder → assemble a project"* idea made real. That
backlog item named its own blocker: the Finder is a static page over `file://`
and by browser security cannot touch the filesystem, so creating hard links
"requires a helper / CLI / back-end beyond the browser page". The Project
Manager GUI has a server, so the blocker is gone — but its design rule stands
and is why this module reuses the ingest pieces rather than writing its own:

    linker.create_hardlink   the link (file primary vs folder primary)
    provenance.append_entry  the provenance row
    registry.update_row      the project association
    pending_links            the deferred queue when the mount can't link

A project link made here is therefore byte-for-byte the same kind of thing as a
link made at ingest time — same inode, same provenance shape, same recovery
path. `/raw/` is never written: the only writes are hard links FROM raw, rows in
`registries/`, and files inside the project folder.

WHAT AN IMPORT IS. An acquisition already exists and is already registered; an
import only says "this project also contains it". So it is:
  1. a hard link in `<project>/raw_linked/` (zero extra storage), and
  2. a `provenance.csv` row, and
  3. the project's id added to `registry_raw.project_id` (a `;`-separated
     list — see ingest/project_ids.py).
Nothing is copied and nothing in `/raw/` moves.
"""

import os
import sys
from datetime import datetime, timezone

from ingest import linker, locking, pending_links, provenance, registry
from ingest import project_ids as pids

# Illegal in a single Windows/SMB path component. A link name comes from
# `original_name`, which for some ecosystems carries a staging-relative PATH
# (that is why the resolver basenames it) — an unsanitised value would try to
# create nested directories under raw_linked/, or just fail.
_ILLEGAL = set('\\/:*?"<>|')

PENDING_STANDIN_SUFFIX = ".PENDING-LINK.txt"

# What `plan` can say about one candidate acquisition.
ST_NEW = "new"                     # will be linked
ST_ALREADY = "already-in-project"  # this project is already on the row
ST_COLLISION = "collision"         # another link in raw_linked/ owns the name
ST_NO_RAW = "raw-missing"          # canonical_path resolves to nothing on disk


def sanitize_link_name(name):
    """A link name that is a legal single path component (or "")."""
    name = (name or "").replace("\\", "/").rstrip("/")
    name = name.split("/")[-1]                    # basename, like the resolver
    name = "".join(c for c in name if c not in _ILLEGAL and ord(c) >= 32)
    return name.strip().strip(".")


def default_link_name(row):
    """The link name to propose for a registry row.

    Ingest derives this from the recipe's `link_filename:` template; an import
    has no recipe, so it uses what ingest itself falls back to — the row's
    `original_name` — basenamed and sanitised. The ACQ-ID is the last resort so
    a row with a blank/unusable `original_name` still gets a usable name rather
    than silently no link.

    The GUI shows this and lets the researcher change it before committing:
    the name is what they will see in their project folder every day, and only
    they know what it should say.
    """
    return sanitize_link_name(row.get("original_name")) or (
        row.get("acq_id") or "").strip()


def resolve_raw_primary(nas_root, row):
    """``(abs_path, kind)`` for the acquisition's primary entity.

    Lifted verbatim from the ingest's Step-12 dispatch (`ingest_raw.py`) so a
    link made here points at exactly what a link made at ingest points at.
    Three branches, and the third is the one that is easy to miss:

      folder primary, `primary_file_name != acq_id`  -> `<acq>/<ACQ-ID>.data`
          the NI / MRI v2 layout: an internal data bundle inside the acq folder.
      folder primary, `primary_file_name == acq_id`  -> the acq folder itself
          the LEGACY MRI layout, where the acq folder IS the primary.
      file primary                                   -> `<acq>/<primary_file>`
          microscopy `.czi`, collaborator `.zip`/`.rar`.

    Getting this wrong links the wrong thing — a plausible-looking link to a
    folder that contains the data rather than to the data.
    """
    canonical = (row.get("canonical_path") or "").strip()
    acq_dir = os.path.normpath(os.path.join(nas_root, canonical.lstrip("/")))
    primary = (row.get("primary_file_name") or "").strip()
    kind = (row.get("primary_kind") or "").strip()
    acq_id = (row.get("acq_id") or "").strip()

    if primary and kind == "folder" and primary != acq_id:
        return os.path.join(acq_dir, primary), "folder"
    if primary and kind == "folder":
        return acq_dir, "folder"
    if primary and not primary.endswith("/"):
        return os.path.join(acq_dir, primary), (kind or "file")
    return acq_dir, (kind or "folder")


def plan(nas_root, project, rows, link_names=None):
    """Dry-run the import of `rows` into `project`. Writes nothing.

    `project` is a `registry_projects.csv` row (needs `project_id` +
    `folder_location`). `link_names` optionally overrides the proposed name per
    acq_id. Returns one dict per row: acq_id, link_name, raw_primary,
    primary_kind, status, note.

    Collisions inside one `raw_linked/` are possible (two acquisitions whose
    `original_name` is the same) and are REPORTED, never silently overwritten:
    a hard link that quietly replaced another would detach a researcher's
    existing link from its data with no trace.
    """
    link_names = link_names or {}
    project_id = (project.get("project_id") or "").strip()
    proj_dir = _project_dir(nas_root, project)
    raw_linked = os.path.join(proj_dir, "raw_linked") if proj_dir else None

    # Names already taken in this project's raw_linked/, plus names claimed
    # earlier in THIS batch — two selected acquisitions can collide with each
    # other before either is written.
    taken = set()
    if raw_linked and os.path.isdir(raw_linked):
        taken = {n.lower() for n in os.listdir(raw_linked)}

    out = []
    for row in rows:
        acq_id = (row.get("acq_id") or "").strip()
        name = sanitize_link_name(link_names.get(acq_id)) or default_link_name(row)
        primary, kind = resolve_raw_primary(nas_root, row)

        if pids.has_project_id(row.get("project_id"), project_id):
            status, note = ST_ALREADY, "Already in this project — nothing to do."
        elif not os.path.exists(primary):
            status, note = ST_NO_RAW, f"Raw data not found on the share: {primary}"
        elif not name:
            status, note = ST_COLLISION, "No usable link name — type one."
        elif name.lower() in taken:
            status, note = ST_COLLISION, (
                f"'{name}' already exists in this project's raw_linked/ — "
                f"choose a different name.")
        else:
            status, note = ST_NEW, ""
            taken.add(name.lower())

        out.append({
            "acq_id": acq_id,
            "link_name": name,
            "raw_primary": primary,
            "primary_kind": kind,
            "status": status,
            "note": note,
            "original_name": row.get("original_name", ""),
            "instrument": row.get("instrument", ""),
            "acquisition_datetime": row.get("acquisition_datetime", ""),
            "existing_projects": pids.split_project_ids(row.get("project_id")),
        })
    return out


def _project_dir(nas_root, project):
    rel = (project.get("folder_location") or "").strip()
    if not rel:
        return None
    return os.path.normpath(os.path.join(nas_root, rel.lstrip("/")))


def _write_standin(raw_linked_dir, link_name, acq_id, raw_primary_rel):
    """Drop the visible `<link>.PENDING-LINK.txt` marker.

    Borrowed from the ingest's deferred-link path, and it matters more here: a
    researcher who imports twenty acquisitions on a machine whose mount cannot
    hard-link needs to see twenty somethings in their folder, not an empty
    directory that looks like the import did nothing. A cheap text pointer, NOT
    a byte copy — the sessions behind these links can be gigabytes. The relink
    pass removes it when it creates the real link.
    """
    try:
        os.makedirs(raw_linked_dir, exist_ok=True)
        ptr = os.path.join(raw_linked_dir, f"{link_name}{PENDING_STANDIN_SUFFIX}")
        if not os.path.exists(ptr):
            with open(ptr, "w", encoding="utf-8") as f:
                f.write(
                    "Placeholder - the real hard link could not be created on "
                    "this machine (this mount has no hard-link support).\n"
                    f"Acquisition: {acq_id}\n"
                    f"Raw data:    {raw_primary_rel}\n"
                    "Your data is safely registered. A data-office relink pass "
                    "(tools/relink_pending.py, run from a hard-link-capable "
                    "machine) replaces this with the real link. Tracked in "
                    "registries/pending_links.csv.\n"
                )
    except OSError:
        pass  # the worklist is the durable record; the pointer is cosmetic


def _add_project_to_rows(nas_root, acq_ids, project_id, log):
    """Add `project_id` to each acquisition's `project_id` cell — ONE pass.

    Deliberately not `registry.update_row` per acquisition: that reads and
    rewrites the whole ~13,500-row registry each time, so a 20-acquisition
    import would rewrite it twenty times over SMB. This is a single locked
    read-modify-write that publishes all of them atomically.

    Idempotent per the cell rules (`ingest/project_ids.py`): blank -> set;
    already this project -> untouched; already a DIFFERENT project -> appended
    with the existing id kept FIRST, so the original association stays primary.
    Returns the number of rows actually changed.
    """
    import csv
    want = {a for a in acq_ids if a}
    if not want:
        return 0
    registries_dir = os.path.join(nas_root, "registries")
    path = os.path.join(registries_dir, "registry_raw.csv")

    with locking.registry_lock(registries_dir):
        registry.assert_header_compatible(path)
        rows = registry.read_registry(path)
        changed = 0
        for row in rows:
            if (row.get("acq_id") or "").strip() not in want:
                continue
            cell, did = pids.add_project_id(row.get("project_id"), project_id)
            if did:
                row["project_id"] = cell
                changed += 1
        if not changed:
            return 0
        tmp = f"{path}.tmp.{os.getpid()}"
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=registry.REGISTRY_FIELDS)
            w.writeheader()
            for row in rows:
                w.writerow({k: row.get(k, "") for k in registry.REGISTRY_FIELDS})
        os.replace(tmp, path)
    log(f"Recorded the project on {changed} registry row(s).")
    return changed


def import_acquisitions(nas_root, project, rows, creator, link_names=None,
                        log=None, tool_name="project_manager"):
    """Link `rows` into `project`. Returns a summary dict.

    `creator` is the one genuinely user-supplied provenance field — ingest
    fills it from the recipe's `operator:`, which an import has no equivalent
    of. Everything else derives.

    Per acquisition, in this order:
      1. hard link (or folder of per-file hard links) via `linker.create_hardlink`
      2. provenance row (idempotent on `output_path`)
      3. — after the loop — one locked pass adding the project to each
         `registry_raw.project_id`

    On `OSError` the acquisition is queued to `registries/pending_links.csv`,
    a stand-in is written, and the batch CARRIES ON. That is the case where the
    machine running this can reach the NAS over a mount that cannot hard-link
    (macOS over SMB returns ENOTSUP; a UNC path can behave the same). The
    acquisition is still associated with the project and its data is still
    registered — the import did NOT fail, and the summary says so in those
    words so nobody deletes and retries something that worked.

    Returns: {linked, queued, skipped, failed, results[], project_id}
    """
    log = log or (lambda msg, level="INFO": None)
    project_id = (project.get("project_id") or "").strip()
    proj_dir = _project_dir(nas_root, project)
    if not proj_dir or not os.path.isdir(proj_dir):
        raise ValueError(
            f"Project {project_id} has no folder on the share. It was closed "
            f"and its folder deleted; data cannot be imported into it."
        )
    raw_linked = os.path.join(proj_dir, "raw_linked")
    prov_path = os.path.join(proj_dir, "provenance.csv")
    registries_dir = os.path.join(nas_root, "registries")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    software = provenance.software_version_string(f"{tool_name}.py")

    planned = plan(nas_root, project, rows, link_names=link_names)
    by_id = {(r.get("acq_id") or "").strip(): r for r in rows}

    results = []
    associate = []          # acq_ids to record on the registry (linked OR queued)
    counts = {"linked": 0, "queued": 0, "skipped": 0, "failed": 0}

    for item in planned:
        acq_id = item["acq_id"]
        if item["status"] != ST_NEW:
            counts["skipped"] += 1
            # An acquisition already in this project still counts as "in the
            # project" — no work, no complaint.
            results.append({**item, "outcome": "skipped"})
            log(f"{acq_id}: {item['note'] or item['status']}", "WARN")
            continue

        link_name = item["link_name"]
        raw_primary = item["raw_primary"]
        try:
            link_path = linker.create_hardlink(proj_dir, link_name, raw_primary)
        except OSError as e:
            _queue(nas_root, registries_dir, raw_linked, acq_id, project_id,
                   link_name, raw_primary, item["primary_kind"], e, log)
            counts["queued"] += 1
            associate.append(acq_id)
            results.append({**item, "outcome": "queued",
                            "note": f"{type(e).__name__}: {e}"})
            continue
        except Exception as e:  # noqa: BLE001 — anything else is a real failure
            counts["failed"] += 1
            results.append({**item, "outcome": "failed", "note": str(e)})
            log(f"{acq_id}: could not create the link: {e}", "ERROR")
            continue

        is_dir_link = os.path.isdir(link_path)
        log(f"{acq_id} -> raw_linked/{link_name}"
            f"{' (folder of per-file hard links)' if is_dir_link else ''}")

        # Provenance: mirrors the ingest Step-12 entry shape so a project's
        # provenance.csv reads the same whether the link came from an ingest or
        # from here. Idempotent on output_path.
        row = by_id.get(acq_id, {})
        try:
            fid = provenance.append_entry(prov_path, {
                "output_path":         f"raw_linked/{link_name}",
                "output_name":         link_name,
                "file_type":           "hardlink-folder" if is_dir_link else "hardlink",
                "date_created":        today,
                "creator":             creator or "",
                "input_refs":          acq_id,
                "process_description": (
                    "Added to this project with the Project Manager: folder of "
                    "per-file hard links to raw acquisition"
                    if is_dir_link else
                    "Added to this project with the Project Manager: hard link "
                    "to raw acquisition"),
                "software_version":    software,
                "parameters_ref":      row.get("ingest_config", "") or "",
                "lab_notebook_ref":    "",
                "notes":               "",
            })
            if fid:
                log(f"  provenance {fid}")
        except Exception as e:  # noqa: BLE001 — the link is already made
            log(f"{acq_id}: link created but provenance could not be written: "
                f"{e}", "WARN")

        counts["linked"] += 1
        associate.append(acq_id)
        results.append({**item, "outcome": "linked"})

    if associate:
        _add_project_to_rows(nas_root, associate, project_id, log)

    return {**counts, "results": results, "project_id": project_id}


def _queue(nas_root, registries_dir, raw_linked, acq_id, project_id, link_name,
           raw_primary, primary_kind, exc, log):
    """Defer one un-makeable link to `registries/pending_links.csv`."""
    raw_primary_rel = "/" + os.path.relpath(raw_primary, nas_root).replace(os.sep, "/")
    errno_s = f" [Errno {exc.errno}]" if getattr(exc, "errno", None) else ""
    try:
        pending_links.append_pending_link(
            registries_dir,
            acq_id=acq_id,
            project_id=project_id,
            link_name=link_name,
            raw_primary_canonical=raw_primary_rel,
            primary_kind=primary_kind or (
                "folder" if os.path.isdir(raw_primary) else "file"),
            reason=f"{type(exc).__name__}: {exc}{errno_s}",
            host_os=sys.platform,
        )
        log(f"{acq_id}: this machine cannot create hard links here — queued for "
            f"a data-office relink pass.", "WARN")
    except Exception as e:  # noqa: BLE001 — never fail an import over the queue
        log(f"{acq_id}: could not queue the deferred link: {e}", "ERROR")
    _write_standin(raw_linked, link_name, acq_id, raw_primary_rel)


def summary_sentence(result):
    """One plain-language line for the researcher, in the UI's words.

    Written out here rather than in the page so the CLI and the GUI say the
    same thing — and because the queued case is the one where a badly-worded
    summary makes someone delete and retry an import that actually worked.
    """
    bits = []
    if result["linked"]:
        bits.append(f"{result['linked']} added")
    if result["queued"]:
        bits.append(
            f"{result['queued']} registered, links pending — your data is safely "
            f"recorded in the project; this machine's connection to the share "
            f"cannot create the file links, so the data office completes them")
    if result["skipped"]:
        bits.append(f"{result['skipped']} skipped")
    if result["failed"]:
        bits.append(f"{result['failed']} failed")
    return "; ".join(bits) or "nothing to do"
