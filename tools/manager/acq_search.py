"""Server-side acquisition search for the import-from-raw picker.

Deliberately NOT the Finder artifact. `registries/index.html` is a ~19 MB
self-contained page with the entire registry inlined as JSON, built to be
double-clicked over SMB with no server at all. This tool HAS a server, so
re-rendering that page inside another page — or parsing 19 MB of embedded
JSON — would be paying its cost to buy nothing. What is reused is the *idiom*
(a table you type into) and the *code* (`find_acq`, which already implements
exactly the filters the Finder exposes). Checkbox selection stays client-side.

CACHING. `registry_raw.csv` is ~13,500 rows over SMB; re-reading it on every
keystroke would make the picker feel broken. The records are held in memory and
re-read only when the file's mtime/size changes, so an ingest running in another
window is picked up without a restart, and a burst of typing costs one read.
"""

import os
import threading

import find_acq

# One process, one cache. Guarded because Flask serves requests on threads.
_LOCK = threading.Lock()
_CACHE = {}          # nas_root -> {"stamp": (mtime, size), "records", "projects"}

# How many rows one response may carry. The picker is for choosing tens of
# acquisitions, not for browsing all 13,500; the count of TOTAL matches is
# always reported so a too-broad filter is visible rather than silently cut.
PAGE_LIMIT = 200


def _stamp(nas_root):
    out = []
    for name in ("registry_raw.csv", "registry_projects.csv"):
        p = os.path.join(nas_root, "registries", name)
        try:
            st = os.stat(p)
            out.append((st.st_mtime_ns, st.st_size))
        except OSError:
            out.append(None)
    return tuple(out)


def load(nas_root, force=False):
    """``(records, projects_index)`` for a NAS root, cached on registry mtime."""
    nas_root = os.path.normpath(nas_root)
    stamp = _stamp(nas_root)
    with _LOCK:
        hit = _CACHE.get(nas_root)
        if hit and not force and hit["stamp"] == stamp:
            return hit["records"], hit["projects"]
    records, proj_idx = find_acq.build_records(nas_root)
    with _LOCK:
        _CACHE[nas_root] = {"stamp": stamp, "records": records,
                            "projects": proj_idx}
    return records, proj_idx


def invalidate(nas_root=None):
    """Drop the cache (after an import writes project_id back to the registry)."""
    with _LOCK:
        if nas_root:
            _CACHE.pop(os.path.normpath(nas_root), None)
        else:
            _CACHE.clear()


def search(nas_root, *, query="", instrument="", researcher="", subject="",
           anatomy="", project="", since="", until="", exclude_project="",
           offset=0, limit=PAGE_LIMIT):
    """Filtered, paged acquisitions. Returns ``{total, rows, instruments}``.

    Every filter is `find_acq.matches`, so the picker and the Finder (and the
    CLI) agree on what a query means — one implementation, no drift.

    `exclude_project` hides acquisitions already in the project being imported
    INTO, so the list shows what can actually be added. They are not silently
    dropped from the count: `already_in_project` reports how many were hidden.
    """
    records, _ = load(nas_root)
    hits = [r for r in records if find_acq.matches(
        r, query=query, instrument=instrument, researcher=researcher,
        subject=subject, anatomy=anatomy, project=project,
        since=since, until=until)]

    already = 0
    if exclude_project:
        keep = []
        for r in hits:
            if exclude_project in (r.get("_project_ids") or []):
                already += 1
            else:
                keep.append(r)
        hits = keep

    # Newest first — the same default the Finder uses, and what someone
    # assembling a project almost always wants.
    hits.sort(key=lambda r: (r.get("acquisition_datetime") or ""), reverse=True)

    offset = max(0, int(offset or 0))
    limit = max(1, min(int(limit or PAGE_LIMIT), PAGE_LIMIT))
    page = hits[offset:offset + limit]

    return {
        "total": len(hits),
        "already_in_project": already,
        "offset": offset,
        "limit": limit,
        "instruments": sorted({(r.get("instrument") or "") for r in records} - {""}),
        "rows": [_row(r) for r in page],
    }


def _row(r):
    """The columns the picker shows — the Finder's, minus what it can't use."""
    return {
        "acq_id": r.get("acq_id", ""),
        "date": (r.get("acquisition_datetime") or "")[:10],
        "instrument": r.get("instrument", ""),
        "modalities": r.get("modalities_in_study", ""),
        "researcher": r.get("researcher", ""),
        "operator": r.get("operator", ""),
        "sample_id": r.get("sample_id", ""),
        "subject_ids": r.get("subject_ids", ""),
        "sample_type": r.get("sample_type", ""),
        "anatomical_entity": r.get("anatomical_entity", ""),
        "original_name": r.get("original_name", ""),
        "size_mb": r.get("file_size_mb", ""),
        "projects": r.get("_project_ids") or [],
        "project_names": r.get("_project_name", ""),
    }


def rows_for(nas_root, acq_ids):
    """The full registry rows for the selected acq_ids, in the given order.

    Read straight from the cached records (which are the registry rows plus
    derived helpers), so the import engine works with the same values the
    picker showed.
    """
    records, _ = load(nas_root)
    by_id = {(r.get("acq_id") or "").strip(): r for r in records}
    return [by_id[a] for a in acq_ids if a in by_id]
