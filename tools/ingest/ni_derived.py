"""ni_derived.py -- NI files that are DERIVED, not acquired: placed in the project, never in /raw/.

A Molecubes CT can carry a reconstruction folder holding only `ATTMAP.dcm`: the CT converted
into PET attenuation coefficients on the PET grid, an input to the PET reconstruction. It is a
derivative of the CT, not another reconstruction of it, so it is not raw and gets no ACQ-ID
(Ryan, 2026-10-08). On irene's box tree that was 52 of 224 recon folders, every one in a CT
scan and never mixed with a real reconstruction.

Where it goes is the existing standard for a derivative: `retire_acquisition.py`'s default and
05_PROJECTS §3 (`outputs/` = "results worth keeping: figures, derived images, reports"):

    <project>/outputs/derived/CT_<subject>_<YYYYMMDD>_<timestamp>_recon<n>_ATTMAP.dcm

named like the scan's own `raw_linked/` link so the two sit side by side, copied and verified
by SHA-256, never overwriting, and recorded in the project's provenance.csv with `input_refs` =
the ACQ-IDs of the scan it was derived from. It waits (a later sync places it) until at least
one reconstruction of that scan is registered, so the record always points at real raw data.

The live sync calls `attenuation_map_files` while fanning out reconstructions (ingest/config.py)
and `place` after its commit (operator/ni_ingest.py). Nothing here writes outside the NAS root.
"""
import os
import re
import shutil
from datetime import datetime, timezone

from . import checksum, linker, project_naming, provenance

SUBFOLDER = ("outputs", "derived")          # = retire_acquisition.DEFAULT_SUBFOLDER
_ATTMAP = re.compile(r"^ATTMAP[^/\\]*\.dcm$", re.IGNORECASE)
NOTES_TAG = "ni-live: derived file (attenuation map), not an acquisition"
# The plain form of provenance.software_version_string(): no `git` call, because this runs on
# the NI Mac, where nothing may be written outside the NAS and the staged code folder.
SOFTWARE = "ni_ingest.py (gjesus3-pilot tools)"


def attenuation_map_files(recon_bucket):
    """The DICOM src_relpaths when a recon folder holds ONLY attenuation maps, else []."""
    rels = [(d.get("src_relpath") or "").replace("\\", "/")
            for d in (recon_bucket or {}).get("dicoms") or []]
    if rels and all(_ATTMAP.match(os.path.basename(r)) for r in rels):
        return rels
    return []


def make_item(case, rel_match, idx, files):
    """What `place` needs, taken from the (corrected, resolved) case of the scan."""
    d = case.get("discovered") or {}
    return {
        "source_path": case.get("source_path") or "",
        "original_name": f"{rel_match}/recon_{idx}",
        "recon_idx": str(idx),
        "files": list(files),
        "modality": (d.get("modality") or "").upper(),
        "subject": d.get("subject") or "",
        "ts14": (d.get("acq_datetime_full") or "")[:14],
        "project_name": case.get("project_name") or "",
        "operator": case.get("operator") or "",
    }


def dest_name(item, src_relpath):
    ts = item["ts14"]
    return (f"{item['modality']}_{item['subject']}_{ts[:8]}_{ts}_recon{item['recon_idx']}_"
            f"{os.path.basename(src_relpath)}")


def _scan_acq_ids(registry_csv):
    """{(ts14, instrument): [ACQ-ID, ...]} for every NI row -- what a derivative ties back to."""
    import csv
    out = {}
    if not os.path.exists(registry_csv):
        return out
    with open(registry_csv, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            ts = "".join(c for c in (row.get("acquisition_datetime") or "") if c.isdigit())[:14]
            inst = (row.get("instrument") or "").strip().upper()
            if len(ts) == 14 and row.get("acq_id"):
                out.setdefault((ts, inst), []).append(row["acq_id"])
    return out


def place(items, nas_root, log, dry_run=False):
    """Copy each derived file into its project's outputs/derived/ and record it in provenance.

    Returns {"placed": n, "already": n, "waiting": [...], "problems": [...]}.
    - Idempotent and light on the box: a file already there with the same SIZE is left alone,
      with no hashing, because every sync passes over every derived file. Bytes are verified by
      SHA-256 only when a file is actually copied. A different file under the name is never
      overwritten.
    - dry_run: reads only. It counts what a real sync would place, including files whose scan
      or project this same sync would create first.
    """
    res = {"placed": 0, "already": 0, "waiting": [], "problems": []}
    if not items:
        return res
    projects_csv = os.path.join(nas_root, "registries", "registry_projects.csv")
    # The full registry read is only needed to tie a file to its raw, i.e. when placing.
    scans = {} if dry_run else _scan_acq_ids(
        os.path.join(nas_root, "registries", "registry_raw.csv"))
    folders = {}                                  # project name -> folder_location (one read each)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for it in items:
        refs = sorted(scans.get((it["ts14"], it["modality"]), []))
        name = project_naming.normalize_project_name(it["project_name"])
        if name not in folders:
            folders[name] = linker.resolve_project(projects_csv, name)[2]
        folder_rel = folders[name]
        pdir = (os.path.normpath(os.path.join(nas_root, folder_rel.lstrip("/")))
                if folder_rel else None)
        if not dry_run and not refs:
            res["waiting"].append(f"{it['original_name']}: no reconstruction of that scan is "
                                  f"registered yet; placed on a later sync")
            continue
        if not dry_run and not pdir:
            res["waiting"].append(f"{it['original_name']}: project '{name}' does not exist yet; "
                                  f"placed on a later sync")
            continue
        for rel in it["files"]:
            src = os.path.join(it["source_path"], *rel.split("/"))
            out_name = dest_name(it, rel)
            dest = os.path.join(pdir, *SUBFOLDER, out_name) if pdir else None
            shown = f"{name}/{'/'.join(SUBFOLDER)}/{out_name}"
            try:
                if dest and os.path.exists(dest):
                    if os.path.getsize(dest) != os.path.getsize(src):
                        res["problems"].append(f"{shown} exists with different content; "
                                               f"not overwritten")
                    else:
                        res["already"] += 1
                    continue
                if dry_run:
                    res["placed"] += 1
                    continue
                src_hash = checksum.sha256_file(src)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                partial = dest + ".partial"
                shutil.copyfile(src, partial)
                if checksum.sha256_file(partial) != src_hash:
                    os.remove(partial)
                    res["problems"].append(f"{shown}: copy failed verification; removed")
                    continue
                os.replace(partial, dest)
                res["placed"] += 1
                log(f"placed derived file: {shown} (from {it['original_name']})")
                provenance.append_entry(os.path.join(pdir, "provenance.csv"), {
                    "output_path": f"{'/'.join(SUBFOLDER)}/{out_name}",
                    "output_name": out_name,
                    "file_type": os.path.splitext(out_name)[1] or "file",
                    "date_created": today,
                    "creator": it["operator"],
                    "input_refs": ";".join(refs),
                    "process_description": (
                        f"CT attenuation map, derived from the {it['modality']} scan "
                        f"{it['ts14']} ({'; '.join(refs)}) for PET attenuation correction. "
                        f"Copied from the acquisition box by the NI live sync; not an "
                        f"acquisition, so it is not in /raw/."),
                    "software_version": SOFTWARE,
                    "parameters_ref": f"{it['original_name']}/{os.path.basename(rel)}",
                    "lab_notebook_ref": "",
                    "notes": NOTES_TAG,
                })
            except OSError as e:
                res["problems"].append(f"{shown}: {e}")
    return res
