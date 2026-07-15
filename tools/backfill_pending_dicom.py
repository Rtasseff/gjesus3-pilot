#!/usr/bin/env python3
"""backfill_pending_dicom.py — enrol the pre-2026-06-24 no-DICOM MRI placeholders
into `registries/pending_dicom_regen.csv`.

WHY THIS EXISTS. The invariant is: *no DICOM-less acquisition should exist without
being registered somewhere as needing a Dicomifier pass.* Today it does not hold.
`ingest_raw.py` queues no-DICOM `mri_paravision_v2` exams to the worklist, but that
mechanism landed 2026-06-24 (`6dce5f9`) and every existing placeholder was ingested
2026-06-13/14 — ten days earlier. No MRI has been ingested since, so the worklist
file has never even been created, and 612 empty `<ACQ-ID>.data/` placeholders sit on
the NAS registered nowhere. They are findable and fully sidecar'd; only their pixels
are missing, and nothing tracks that.

This is a one-time catch-up for those rows. Forward ingests enrol themselves — both
producing configs use `copy_strategy: mri_paravision_v2`, which is exactly the branch
that queues, so a re-run today would file them correctly and this tool would be a
no-op on them.

It writes the SAME rows the live path would have written, from the same sources:

  acq_id / original_name / canonical_path / ingest_config  <- registry_raw.csv
  paravision_version / nonimage_marker                     <- the acquisition's
                                                              metadata.json
                                                              (discovered.*)
  reconstructions                                          <- ingest.reconstructions
                                                              in the producing config

NOT every DICOM-less exam is regenerable. A spectroscopy/calibration acquisition
(STEAM/PRESS/WOBBLE) is refused by `paravision_regen` by design, so it is filed
`status=not-applicable` with the matched `nonimage_marker` rather than "pending" —
otherwise the worklist could never drain to zero. Those rows stay listed because
they ARE DICOM-less and must not go invisible; they are the input set for the
separate spectroscopy path. **Drain `status == "pending"`.**

`original_name` is the ParaVision `<study>/<exam>` identity (e.g.
`20220119_081642_jrc220119_m10_1521_1_1/3`) — the handle the regen pass uses to
re-pull from `kenia`, since gjesus3 never archived the raw fid/2dseq bytes. See
`tools/ingest/pending_dicom.py`.

Idempotent on `acq_id` and status-preserving, exactly like `append_pending_dicom`:
re-running refreshes the source/target fields but never resets a row the data office
has already marked "regenerated".

  PYTHONPATH=tools python tools/backfill_pending_dicom.py --nas-root J:/gjesus3-data --dry-run
  PYTHONPATH=tools python tools/backfill_pending_dicom.py --nas-root J:/gjesus3-data --apply
"""
import argparse
import collections
import json
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ingest import paravision_regen, pending_dicom, registry  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _nas_join(nas, share_rel):
    """Share-relative registry path (e.g. '/raw/DICOM/...') -> a local path."""
    return os.path.join(nas, share_rel.strip("/").replace("/", os.sep))


def _recons_for_config(cfg_rel, _cache={}):
    """`ingest.reconstructions` from the config that produced a row.

    Stringified the same way the live call site does (`str(...)`), so a backfilled
    row is byte-identical to one the ingest would have written. Returns "" when the
    config is gone or unreadable — a blank recon selection is honest and the regen
    pass can still find the exam by name.
    """
    if cfg_rel in _cache:
        return _cache[cfg_rel]
    val = ""
    path = os.path.join(REPO_ROOT, cfg_rel.replace("/", os.sep))
    if cfg_rel and os.path.isfile(path):
        try:
            with open(path, encoding="utf-8") as f:
                doc = yaml.safe_load(f) or {}
            ing = doc.get("ingest") or {}
            if "reconstructions" in ing:
                val = str(ing.get("reconstructions", ""))
        except Exception as e:  # noqa: BLE001 — a bad config must not abort the pass
            print(f"  WARN: could not read {cfg_rel}: {e}")
    elif cfg_rel:
        print(f"  WARN: config not found in repo: {cfg_rel} (reconstructions left blank)")
    _cache[cfg_rel] = val
    return val


def _data_dir_is_empty(nas, row):
    """True when the acquisition's <ACQ-ID>.data/ holds no files.

    Trust the disk, not the registry's file_count: only enrol placeholders that are
    genuinely empty *now*. A row whose data has since been filled in must never be
    queued for regeneration.
    """
    acq_dir = _nas_join(nas, row["canonical_path"])
    data_dir = os.path.join(acq_dir, f"{row['acq_id']}.data")
    if not os.path.isdir(data_dir):
        return None  # no .data/ at all — report separately, don't guess
    for _, _, files in os.walk(data_dir):
        if files:
            return False
    return True


def _sidecar_discovered(nas, row):
    p = os.path.join(_nas_join(nas, row["canonical_path"]), "metadata.json")
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f).get("discovered") or {}
    except Exception:
        return {}


def _nonimage_marker(discovered):
    """The STEAM/PRESS/WOBBLE marker for this acquisition, or "".

    The live ingest calls `paravision_regen.is_nonimage_exam(exam_path)`, which
    reads the exam's JCAMP-DX `method`/`acqp`. Those source exams are long gone
    (staging is auto-deleted), so match the same markers against the sidecar's
    `mri_sequence_name` — which the extractor derived from that same JCAMP
    `Method` at ingest (e.g. "Bruker:STEAM"). Same constant, different source, so
    the two classifications cannot drift apart.
    """
    seq = (discovered.get("mri_sequence_name") or "")
    for marker in paravision_regen._NONIMAGE_METHOD_MARKERS:
        if marker.lower() in seq.lower():
            return marker
    return ""


def collect(nas, limit=0):
    """(rows_to_queue, skipped) — the DICOM-less MRI acquisitions needing regen."""
    rows = registry.read_registry(os.path.join(nas, "registries", "registry_raw.csv"))
    cand = [r for r in rows
            if (r.get("instrument") or "").strip() == "MRI"
            and (r.get("file_count") or "").strip() in ("0", "")
            and (r.get("canonical_path") or "").strip()]
    if limit:
        cand = cand[:limit]
    print(f"registry: {len(rows)} acquisitions; {len(cand)} MRI candidates (file_count=0)")

    out, skipped = [], []
    for r in cand:
        empty = _data_dir_is_empty(nas, r)
        if empty is None:
            skipped.append((r["acq_id"], "no <ACQ-ID>.data/ directory"))
            continue
        if not empty:
            skipped.append((r["acq_id"], "data present on disk — not a placeholder"))
            continue
        disc = _sidecar_discovered(nas, r)
        out.append({
            "acq_id": r["acq_id"],
            "original_name": r.get("original_name", ""),
            "reconstructions": _recons_for_config(r.get("ingest_config", "")),
            "canonical_path": r["canonical_path"],
            "paravision_version": disc.get("mri_paravision_version", "") or "",
            "ingest_config": r.get("ingest_config", ""),
            "nonimage_marker": _nonimage_marker(disc),
        })
    return out, skipped


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--nas-root", default=os.environ.get("GJESUS3_ROOT", "J:/gjesus3-data"))
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="report only; write nothing")
    mode.add_argument("--apply", action="store_true", help="write pending_dicom_regen.csv")
    ap.add_argument("--limit", type=int, default=0, help="cap acqs scanned (debug)")
    args = ap.parse_args(argv)

    nas = os.path.normpath(args.nas_root)
    registries_dir = os.path.join(nas, "registries")
    new_rows, skipped = collect(nas, args.limit)

    path = pending_dicom.pending_dicom_path(registries_dir)
    existing = pending_dicom.read_pending_dicom(path)
    print(f"worklist: {path}\n  existing rows: {len(existing)}")
    try:
        pending_dicom._assert_header(path)
    except RuntimeError:
        # A pre-`nonimage_marker` worklist. Every field is re-derived from source
        # below and the file is rewritten whole, so migrating is just carrying the
        # old `status` across — nothing is lost.
        print("  NOTE: legacy header (pre-nonimage_marker) — migrating in place")

    # Same merge semantics as append_pending_dicom, but resolved once and written
    # once rather than re-reading + rewriting the whole file 600+ times over SMB:
    # idempotent on acq_id, and `status` is preserved so a row the data office
    # already marked "regenerated" is never reset.
    by_id = {r.get("acq_id"): r for r in existing}
    queued_at = pending_dicom._now_iso()
    added = refreshed = corrected = 0
    for n in new_rows:
        status = "not-applicable" if n["nonimage_marker"] else "pending"
        cur = by_id.get(n["acq_id"])
        if cur:
            cur.update(n)
            cur["queued_datetime"] = queued_at
            # Only "regenerated" is sacred; a "pending" row we now know is
            # non-image is a correction, not a reset (see pending_dicom).
            if cur.get("status") in ("", "pending", None):
                if cur.get("status") == "pending" and status == "not-applicable":
                    corrected += 1
                cur["status"] = status
            refreshed += 1
        else:
            by_id[n["acq_id"]] = dict(n, queued_datetime=queued_at, status=status)
            added += 1

    merged = list(by_id.values())
    by_pv = collections.Counter(r.get("paravision_version", "") for r in merged)
    by_status = collections.Counter(r.get("status", "") for r in merged)
    by_marker = collections.Counter(r.get("nonimage_marker") or "(image)" for r in merged)
    print(f"  to add: {added}   to refresh: {refreshed}   "
          f"pending->not-applicable corrections: {corrected}   total after: {len(merged)}")
    print(f"  paravision_version split: {dict(by_pv)}")
    print(f"  status split:             {dict(by_status)}")
    print(f"  nonimage_marker split:    {dict(by_marker)}")
    print(f"  -> the DRAIN SET (status=pending) is {by_status.get('pending', 0)} exams")
    missing_pv = [r["acq_id"] for r in merged if not r.get("paravision_version")]
    if missing_pv:
        print(f"  WARN: {len(missing_pv)} row(s) without a paravision_version "
              f"(regen must search both PV roots): {missing_pv[:5]}")
    if skipped:
        print(f"  skipped {len(skipped)}:")
        for a, why in skipped[:10]:
            print(f"    {a}: {why}")

    if not args.apply:
        print("\n[DRY RUN] nothing written. Re-run with --apply to write the worklist.")
        return 0

    pending_dicom._write_all(path, merged)
    print(f"\nwrote {path}  ({len(merged)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
