"""filebrowse.py — the backend for the in-page folder browser.

The server-side counterpart of `static/folder_browser.js`, shared by BOTH local
GUIs (the operator ingest app and the Project Manager). It was inlined in the
operator app's `/api/listdir`; the Project Manager needs exactly the same
listing, and two copies of a directory lister that must agree on sort order and
truncation is the drift the shared JS component was created to end.

Why a custom lister at all: the OS folder-chooser dialog shows ONLY folders, so
every folder looks empty and operators could not tell where they were. This
returns folders AND files — files greyed for context in folder-pick mode, and
tickable in the Project Manager's file-pick mode.

SORT ORDER matters and is done HERE, not in the browser. Instrument and batch
folders are named by date (`…\\AxioScan\\20260522`), so reverse-name IS
newest-first. The sort runs BEFORE the entry cap, so a reversed view of a huge
folder shows its true last entries; reversing the truncated list client-side
would silently show the wrong end.

These are LOCAL apps listing the machine's own filesystem, which is the point —
that is how a researcher points at a folder on their D: drive or a mounted
share.
"""

import os
import string

# Names that are never a useful target and only clutter the browser.
HIDE_NAMES = {"system volume information", "$recycle.bin"}

# Cap the entries returned for one folder (a huge data dir would bloat the page).
BROWSE_LIMIT = 3000


def list_drives():
    """Available drive roots (Windows) or "/" (POSIX), for the jump bar."""
    if os.name == "nt":
        return [f"{c}:\\" for c in string.ascii_uppercase if os.path.exists(f"{c}:\\")]
    return ["/"]


def list_folder(raw_path, desc=False, with_size=False):
    """One folder's contents, in the shape `folder_browser.js` expects.

    Returns {path, parent, entries[{name, is_dir, size?}], desc, drives,
             error, truncated}. A bad path is answered with the home folder
    AND an `error` string rather than an exception — the browser decides
    whether that is worth showing (a remembered folder that has since gone
    away is not the user's mistake).

    `with_size` adds each file's size, which the file-pick mode shows so
    someone choosing what to copy onto the share can see what it costs.
    """
    raw = (raw_path or "").strip()
    path = os.path.abspath(raw) if raw else os.path.expanduser("~")

    out = {"path": path, "parent": None, "entries": [], "desc": bool(desc),
           "drives": list_drives(), "error": None, "truncated": False}

    if not os.path.isdir(path):
        out["error"] = f"Not a folder: {path}"
        path = os.path.expanduser("~")
        out["path"] = path

    parent = os.path.dirname(path)
    out["parent"] = (parent if parent
                     and os.path.normpath(parent) != os.path.normpath(path)
                     else None)

    try:
        entries = []
        with os.scandir(path) as it:
            for e in it:
                if e.name.lower() in HIDE_NAMES:
                    continue
                try:
                    is_dir = e.is_dir()
                except OSError:
                    is_dir = False
                item = {"name": e.name, "is_dir": is_dir}
                if with_size and not is_dir:
                    try:
                        item["size"] = e.stat().st_size
                    except OSError:
                        item["size"] = None
                entries.append(item)
        # Case-insensitive name order (flipped by `desc`), then a STABLE pass
        # lifting folders above files — the grouping never flips, only the
        # name order does.
        entries.sort(key=lambda x: x["name"].lower(), reverse=bool(desc))
        entries.sort(key=lambda x: not x["is_dir"])
        if len(entries) > BROWSE_LIMIT:
            out["truncated"] = True
            entries = entries[:BROWSE_LIMIT]
        out["entries"] = entries
    except OSError as ex:
        out["error"] = str(ex)
    return out
