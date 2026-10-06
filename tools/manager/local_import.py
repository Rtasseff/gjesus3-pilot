"""Copy files from local or mounted storage into a project — "import from local".

The other half of importing. Unlike the raw import, this one **copies**: the
files are not in `/raw/` and there is nothing to hard-link to, so every byte
lands on the NAS for real. Two consequences drive the design:

* **Space is consumed.** A raw import costs nothing (same inode); this can fill
  the share. The total is checked against free space BEFORE anything is copied,
  because a half-copied batch that dies on ENOSPC leaves truncated files that
  look complete.
* **A destination file may already exist.** It is never silently replaced —
  `plan` reports the clash and the caller must pass `overwrite` for that file
  by name. This is the house pattern the recipe-overwrite flow established: a
  409-style refusal the UI turns into an explicit "replace?" prompt that names
  the file.

Copies are `shutil.copy2` (content + mtime), never moves — the researcher's own
copy stays where it was. Every copied file gets a `provenance.csv` row recording
where it came from, which is the whole point of routing this through a tool
instead of dragging files in Explorer.
"""

import os
import shutil
from datetime import datetime, timezone

from ingest import project_layout, provenance

# Where a copy may land. The recommended subfolders, plus the project root.
# `raw_linked/` is deliberately NOT offered: it is tool-managed and holds links
# to immutable raw data — dropping a loose copy in there would make a
# researcher's "these are my raw acquisitions" folder stop meaning that.
DEST_CHOICES = ["working", "outputs", "metadata", ""]
DEFAULT_DEST = "working"

# Leave this much room on the share rather than filling it to the last byte.
FREE_SPACE_MARGIN_BYTES = 1 * 1024 * 1024 * 1024   # 1 GB

ST_NEW = "new"
ST_EXISTS = "exists"          # destination occupied — needs an explicit replace
ST_MISSING = "source-missing"
ST_DUPLICATE = "duplicate"    # two selected sources land on the same name


def _dest_dir(project_dir, subfolder):
    sub = (subfolder or "").strip().strip("/\\")
    if sub and sub not in DEST_CHOICES:
        raise ValueError(
            f"Destination must be one of "
            f"{', '.join(d or 'the project root' for d in DEST_CHOICES)}."
        )
    return os.path.join(project_dir, sub) if sub else project_dir


def plan(project_dir, sources, subfolder=DEFAULT_DEST, overwrite=()):
    """Dry-run a copy. Writes nothing. Returns ``(items, totals)``.

    `sources` are absolute paths to FILES (a folder is reported, not walked —
    "tick the files you want" is the interaction, and silently pulling in a
    tree's worth of files is not what was ticked).

    `overwrite` is the set of destination basenames the caller has explicitly
    agreed to replace.
    """
    dest_dir = _dest_dir(project_dir, subfolder)
    overwrite = {o.lower() for o in (overwrite or ())}
    seen = {}
    items, total_bytes, copyable = [], 0, 0

    for src in sources:
        src = os.path.abspath(src)
        name = os.path.basename(src.rstrip("/\\"))
        dest = os.path.join(dest_dir, name)
        size = 0
        if not os.path.isfile(src):
            status, note = ST_MISSING, (
                "Not a file (folders are not copied — tick the files inside)."
                if os.path.isdir(src) else "This file is no longer there.")
        else:
            size = os.path.getsize(src)
            low = name.lower()
            if low in seen:
                status, note = ST_DUPLICATE, (
                    f"Two selected files are both called '{name}' — the second "
                    f"would overwrite the first. Import one of them.")
            elif os.path.exists(dest) and low not in overwrite:
                status, note = ST_EXISTS, (
                    f"'{name}' is already in {subfolder or 'the project'}. "
                    f"Confirm to replace it.")
            else:
                status, note = ST_NEW, ""
                total_bytes += size
                copyable += 1
                seen[low] = src

        items.append({
            "source": src, "name": name, "dest": dest, "size": size,
            "status": status, "note": note,
            "replaces": status == ST_NEW and os.path.exists(dest),
        })

    free = None
    try:
        # The project folder exists, so its filesystem is the destination's.
        free = shutil.disk_usage(project_dir).free
    except OSError:
        pass
    fits = free is None or total_bytes + FREE_SPACE_MARGIN_BYTES <= free

    return items, {
        "dest_dir": dest_dir,
        "subfolder": subfolder,
        "count": copyable,
        "bytes": total_bytes,
        "free_bytes": free,
        "fits": fits,
    }


def copy_files(project_dir, sources, creator, subfolder=DEFAULT_DEST,
               overwrite=(), log=None, tool_name="project_manager"):
    """Copy `sources` into the project and write provenance. Returns a summary.

    Refuses the whole batch up front if it would not fit — a partial copy that
    runs out of space leaves truncated files indistinguishable from good ones.

    `creator` is the one field that cannot be derived (who is adding this);
    everything else — the type from the extension, the source path, the date —
    comes from the file itself.
    """
    log = log or (lambda msg, level="INFO": None)
    items, totals = plan(project_dir, sources, subfolder, overwrite)

    if not totals["fits"]:
        raise ValueError(
            f"Not enough room on the share: this would copy "
            f"{_mb(totals['bytes'])} and only {_mb(totals['free_bytes'])} is "
            f"free. Nothing was copied."
        )

    dest_dir = totals["dest_dir"]
    # Create the destination on demand: an older project may not have `working/`
    # yet (none of the 49 live folders did before the backfill).
    os.makedirs(dest_dir, exist_ok=True)
    project_layout.ensure_subfolders(project_dir)

    prov_path = os.path.join(project_dir, "provenance.csv")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    software = provenance.software_version_string(f"{tool_name}.py")

    counts = {"copied": 0, "skipped": 0, "failed": 0}
    results = []
    for item in items:
        if item["status"] != ST_NEW:
            counts["skipped"] += 1
            results.append({**item, "outcome": "skipped"})
            log(f"{item['name']}: {item['note']}", "WARN")
            continue
        try:
            # copy2, never move: the researcher's own copy stays put.
            shutil.copy2(item["source"], item["dest"])
        except OSError as e:
            counts["failed"] += 1
            results.append({**item, "outcome": "failed", "note": str(e)})
            log(f"{item['name']}: copy failed: {e}", "ERROR")
            continue

        rel = os.path.relpath(item["dest"], project_dir).replace(os.sep, "/")
        ext = os.path.splitext(item["name"])[1].lstrip(".").lower()
        try:
            fid = provenance.append_entry(prov_path, {
                "output_path":         rel,
                "output_name":         item["name"],
                "file_type":           ext or "file",
                "date_created":        today,
                "creator":             creator or "",
                "input_refs":          item["source"],
                "process_description": "Copied from local storage",
                "software_version":    software,
                "parameters_ref":      "",
                "lab_notebook_ref":    "",
                "notes":               "",
            })
            if fid:
                log(f"{item['name']} -> {rel}  (provenance {fid})")
            else:
                # Idempotent on output_path: a replaced file keeps its original
                # row rather than growing a second one for the same path.
                log(f"{item['name']} -> {rel}  (replaced; provenance row kept)")
        except Exception as e:  # noqa: BLE001 — the file is already copied
            log(f"{item['name']}: copied, but provenance could not be written: "
                f"{e}", "WARN")

        counts["copied"] += 1
        results.append({**item, "outcome": "copied"})

    return {**counts, "results": results, "dest_dir": dest_dir,
            "bytes": totals["bytes"]}


def _mb(n):
    if n is None:
        return "an unknown amount"
    for unit in ("bytes", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "bytes" else f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} TB"
