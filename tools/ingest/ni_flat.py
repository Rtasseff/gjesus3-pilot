#!/usr/bin/env python3
"""ni_flat.py — discovery for the flat Molecubes DICOMs staged off `S:\\gnuclear`.

The live box and the platform archive both hand us a *folder* per acquisition
(`<14digit>_<MODALITY>/recon_<idx>/`), which is what `expand_batch`'s glob-driven
discovery expects. The researcher working space does not: its DICOMs are loose
files at a depth that varies from 0 to 8 levels, frequently copied into several
analysis folders, and sometimes split into one file per dynamic-PET frame.

So discovery here is **fan-in** rather than glob: find every reconstructed DICOM
by its filename, then group the files into acquisitions. It is the mirror image
of the live path's `config.fanout_ni_recons`, which splits one folder into one
case per reconstruction — both end at the same unit, one acquisition per
reconstruction, so the two sources produce registry rows of the same shape.

IDENTITY
--------
    acquisition = (timestamp, modality, algo, recon_idx)

**Directory-independent, and that is the whole point.** The same reconstruction
is copied into as many as 48 folders in this source; 6 appear under two
different year folders. Keying on the path would have produced ~370 duplicate
rows from this source alone. Because the key is derived from the machine-issued
filename, it is also stable across re-runs and comparable with the archive rows
already in production.

`original_name` is set to that key rather than to a relative path. The existing
`(acq_date, original_name)` registry dedup then becomes canonical for free — no
change to `_build_dedupe_index`, which matters because that file is being edited
concurrently on the live-sync branch.

Cross-source dedup against acquisitions already ingested from the platform
archive is done here too (`_registered_scans`), on `(timestamp, modality)` —
deliberately coarser than the acquisition key, because the 132 archive rows
predate the per-reconstruction model and carry no recon index. Coarser means we
may decline to add a second reconstruction of an already-loaded scan; the
alternative — a duplicate row for the same scan — is far worse.
"""
import csv
import os
import re
import sys

_TOOLS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)

import ni_gnuclear_discover as nd  # noqa: E402  (shared path/subject grammar)


def _registered_scans(registry_path):
    """{(ts14, instrument)} already in the registry — the cross-source guard."""
    keys = set()
    if not registry_path or not os.path.exists(registry_path):
        return keys
    try:
        with open(registry_path, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                inst = (row.get("instrument") or "").strip().upper()
                if inst not in ("PET", "CT", "SPECT", "OI"):
                    continue
                digits = "".join(c for c in (row.get("acquisition_datetime") or "")
                                 if c.isdigit())[:14]
                if len(digits) == 14:
                    keys.add((digits, inst))
    except Exception as e:  # noqa: BLE001 — a readable registry is not guaranteed
        print(f"[ni_flat] WARN: could not read {registry_path}: {e}")
    return keys


def dst_basename(filename, recon_idx):
    """Map a source filename onto the box's `.data/` naming.

    `recon<X>.dcm` / `recon<X>_frame<Y>.dcm` — the same shape
    `ingest_raw.copy_ni_acquisition` produces for the archive and live paths, so
    an acquisition looks identical on disk whichever source it came from.
    """
    m = nd.DCM_RE.match(filename)
    if not m:
        return filename
    frame = (m.group("frame") or "")
    if frame:
        return f"recon{recon_idx}_frame{frame}.dcm"
    return f"recon{recon_idx}.dcm"


def discover(staging_dir, registry_path=None, researchers=None,
             require_project=True):
    """Walk `staging_dir` and return (matches, index).

    `matches` is one representative source FILE per acquisition (so the existing
    per-case loop in expand_batch still has a real path to work with); `index`
    maps that path -> everything the case needs.
    """
    by_key = {}
    for dirpath, _dirs, filenames in os.walk(staging_dir):
        for fn in filenames:
            if not fn.lower().endswith(".dcm"):
                continue
            if not nd.DCM_RE.match(fn):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, staging_dir).replace(os.sep, "/")
            row = nd.analyse(rel)
            if not row:
                continue
            by_key.setdefault(row["acq_key"], []).append((full, rel, row))

    registered = _registered_scans(registry_path)
    matches, index = [], {}
    n_skip_registered = n_skip_noproject = 0

    for key in sorted(by_key):
        entries = by_key[key]
        # Canonical entry = shallowest path, then lexicographic. Deeper copies
        # are working copies; the shallowest is consistently the original.
        entries.sort(key=lambda e: (e[1].count("/"), e[1]))
        canon_full, canon_rel, row = entries[0]

        if researchers and row["researcher"].lower() not in researchers:
            continue

        # No animal-protocol code anywhere in the path. 28% of this source is
        # filed by study/tracer name instead ("FDG", "Starget", "ionp", ...).
        # These are NOT malformed, but the project a scan belongs to cannot be
        # guessed — an AE code is a regulatory identifier — so they are held
        # back until a (researcher, series) -> code mapping exists. Dedup is on
        # the machine timestamp, so ingesting them later costs nothing.
        if require_project and not row["project"]:
            n_skip_noproject += 1
            continue

        ts14 = key[:14]
        if (ts14, row["modality"]) in registered:
            n_skip_registered += 1
            continue

        # Members: one file per distinct destination name. Copies of the same
        # file across folders collapse here; genuine per-frame files do not,
        # because their destination names differ.
        members, taken = [], {}
        for full, rel, _r in entries:
            base = dst_basename(os.path.basename(rel), row["recon"])
            if base in taken:
                continue
            taken[base] = rel
            members.append({"src": full, "rel": rel, "dst": base})

        matches.append(canon_full)
        index[canon_full] = {
            "acq_key": key,
            "members": members,
            "discovered": {
                "acq_datetime_full": ts14,
                "acq_date8": ts14[:8],
                "modality": row["modality"],
                "ni_algo": row["algo"],
                "ni_recon_idx": str(row["recon"]),
                "researcher_folder": row["researcher"],
                "subject": row["subject_folder"],
                "series": row["series"],
                "timepoint": row["timepoint"],
                "year_folder": row["year_folder"],
                "source_relpath": canon_rel,
                "parse_flags": row["flags"],
            },
        }

    if n_skip_registered:
        print(f"[ni_flat] {n_skip_registered} acquisition(s) skipped — that scan "
              f"is already in the registry (cross-source dedup on "
              f"(timestamp, modality)).")
    if n_skip_noproject:
        print(f"[ni_flat] {n_skip_noproject} acquisition(s) HELD BACK — no animal-"
              f"protocol code in the path. These need a (researcher, series) -> "
              f"code mapping; run tools/ni_gnuclear_discover.py to list them.")
    print(f"[ni_flat] {len(matches)} acquisition(s) discovered from "
          f"{sum(len(v) for v in by_key.values())} DICOM file(s).")
    return matches, index
