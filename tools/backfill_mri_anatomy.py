#!/usr/bin/env python3
"""backfill_mri_anatomy.py — back-fill the anatomy block on already-ingested
MRI acquisitions using the DRAFT scan-name mapping.

Context (tasks/BACKLOG.md, 2026-06-13): the MRI bulk historical ingest sets
`anatomy` once per batch (template default → `is_whole_body: null`), but MRI is
region-specific (cardiac / brain / ...). This tool reads each MRI acquisition's
`metadata.json` sidecar on the NAS, derives the anatomy region from the captured
scan-name signals (ProtocolName / SeriesDescription / sequence) via the SAME
shared mapping the live ingest now uses (ingest/anatomy_derive.py), and fills
the sidecar's `anatomy` block — and the registry's `anatomical_entity` column —
for any acquisition the operator left unset.

Safe-by-design, mirroring tools/recover_subject_metadata.py:
  - DRY-RUN by default (touches nothing); pass --apply to write.
  - Only fills acquisitions whose anatomy is still UNSET (no region + null
    is_whole_body). Operator-entered / already-derived anatomy is never
    overwritten (use --force to re-derive).
  - Conservative mapping: only high-confidence regions are derived; ambiguous
    scans are left null (see anatomy_derive.py). It NEVER writes a guess.
  - Atomic sidecar write + verify-after-write + rollback on failure.
  - Registry `anatomical_entity` patched under the registry lock.

Run (dry-run preview, all MRI acqs):
    PYTHONPATH=tools python tools/backfill_mri_anatomy.py --nas-root J:/gjesus3-data

Apply, one project:
    PYTHONPATH=tools python tools/backfill_mri_anatomy.py --nas-root J:/gjesus3-data \
        --project PROJ-0003 --apply
"""

import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ on path

from ingest import anatomy_derive, registry as reg, csv_safe, locking  # noqa: E402


def log(msg, level="INFO"):
    print(f"[backfill-anatomy] {level}: {msg}")


def _read_sidecar(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_sidecar(path, sidecar):
    """Atomic sidecar write (temp + os.replace), preserving the 2-space indent
    + trailing newline used elsewhere. The /raw sidecar is immutable-by-policy,
    so the write must never leave a truncated file."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(sidecar, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def _sidecar_path(nas_root, canonical_path):
    """nas_root + a registry canonical_path ('/raw/.../ACQ.../') -> metadata.json."""
    rel = (canonical_path or "").lstrip("/")
    return os.path.normpath(os.path.join(nas_root, rel, "metadata.json"))


def _anatomy_is_unset(anatomy):
    """True if the anatomy block has no region label AND is_whole_body is null."""
    region = anatomy.get("region") or {}
    has_region = bool(isinstance(region, dict) and region.get("label"))
    return (not has_region) and anatomy.get("is_whole_body") is None


def plan_one(sidecar, *, force=False):
    """Decide whether/what to back-fill for one sidecar.

    Returns (outcome, proposed) where outcome is one of:
      "no-mri"       — no mri section (not an MRI acq)
      "no-anatomy"   — no anatomy block (not organism/tissue)
      "already-set"  — anatomy already has region / is_whole_body (skipped)
      "no-derivation"— signals didn't match a confident rule (left null)
      "fill"         — `proposed` anatomy dict ready to write
    """
    if "mri" not in sidecar:
        return "no-mri", None
    anatomy = sidecar.get("anatomy")
    if not isinstance(anatomy, dict):
        return "no-anatomy", None
    if not force and not _anatomy_is_unset(anatomy):
        return "already-set", None
    signals = anatomy_derive.collect_mri_signals(
        (sidecar.get("discovered") or {}), sidecar.get("mri") or {},
    )
    proposed = anatomy_derive.derive_anatomy(
        signals["text_signals"], fov=signals.get("fov"),
    )
    if not proposed:
        return "no-derivation", None
    return "fill", proposed


def _apply_to_sidecar(path, proposed):
    """Write the proposed anatomy fields into the sidecar; verify; rollback on
    failure. Returns (ok, detail)."""
    try:
        sidecar = _read_sidecar(path)
    except Exception as e:
        return False, f"re-read failed: {e}"
    anatomy = sidecar.get("anatomy")
    if not isinstance(anatomy, dict):
        return False, "anatomy block vanished"
    backup = dict(anatomy)
    anatomy["is_whole_body"] = proposed["is_whole_body"]
    anatomy["region"] = proposed["region"]
    anatomy["auto_hint"] = proposed["auto_hint"]
    anatomy["source"] = proposed["source"]
    try:
        _write_sidecar(path, sidecar)
    except Exception as e:
        return False, f"write failed: {e}"
    # Verify-after-write.
    try:
        fresh = _read_sidecar(path).get("anatomy") or {}
    except Exception as e:
        return False, f"verify re-read failed: {e}"
    region = fresh.get("region") or {}
    if region.get("label") != proposed["region"]["label"]:
        sidecar["anatomy"] = backup
        try:
            _write_sidecar(path, sidecar)
        except Exception:
            pass
        return False, "verify-after-write FAILED; rolled back"
    return True, "filled + verified"


def _update_registry(registry_path, registries_dir, updates):
    """Patch the `anatomical_entity` cell for each {acq_id: label} under the
    registry lock; rewrite the CSV atomically. Returns the number of rows
    changed."""
    if not updates:
        return 0
    with locking.registry_lock(registries_dir):
        rows = reg.read_registry(registry_path)
        changed = 0
        for r in rows:
            aid = r.get("acq_id")
            if aid in updates and (r.get("anatomical_entity") or "") != updates[aid]:
                r["anatomical_entity"] = updates[aid]
                changed += 1
        if changed:
            tmp = registry_path + ".tmp"
            with open(tmp, "w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=reg.REGISTRY_FIELDS,
                                   extrasaction="ignore")
                w.writeheader()
                for r in rows:
                    w.writerow({k: r.get(k, "") for k in reg.REGISTRY_FIELDS})
            os.replace(tmp, registry_path)
    return changed


def backfill(nas_root, *, project=None, acq_id=None, apply=False, force=False):
    """Walk the registry, back-fill anatomy on unset MRI acquisitions.

    Returns a counts dict.
    """
    registries_dir = os.path.join(nas_root, "registries")
    registry_path = os.path.join(registries_dir, "registry_raw.csv")
    rows = reg.read_registry(registry_path)
    counts = {"scanned": 0, "filled": 0, "would-fill": 0, "already-set": 0,
              "no-derivation": 0, "no-anatomy": 0, "no-mri": 0,
              "missing-sidecar": 0, "error": 0}
    registry_updates = {}

    for row in rows:
        aid = row.get("acq_id", "")
        if acq_id and aid != acq_id:
            continue
        if project and (row.get("project_hint") or "") != project:
            continue
        path = _sidecar_path(nas_root, row.get("canonical_path", ""))
        if not os.path.isfile(path):
            counts["missing-sidecar"] += 1
            log(f"{aid}: sidecar not found at {path}", "WARN")
            continue
        counts["scanned"] += 1
        try:
            sidecar = _read_sidecar(path)
        except Exception as e:
            counts["error"] += 1
            log(f"{aid}: could not read sidecar: {e}", "ERROR")
            continue

        outcome, proposed = plan_one(sidecar, force=force)
        if outcome in ("no-mri", "no-anatomy", "already-set", "no-derivation"):
            counts[outcome] += 1
            continue

        # outcome == "fill"
        label = proposed["region"]["label"]
        if not apply:
            counts["would-fill"] += 1
            log(f"{aid}: WOULD fill region={label} "
                f"(is_whole_body={proposed['is_whole_body']})")
            continue
        ok, detail = _apply_to_sidecar(path, proposed)
        if ok:
            counts["filled"] += 1
            registry_updates[aid] = label
            log(f"{aid}: filled region={label} ({detail})")
        else:
            counts["error"] += 1
            log(f"{aid}: {detail}", "ERROR")

    if apply and registry_updates:
        n = _update_registry(registry_path, registries_dir, registry_updates)
        log(f"registry: patched anatomical_entity on {n} row(s)")

    return counts


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--nas-root", required=True,
                    help="NAS root (e.g. J:/gjesus3-data) holding registries/ + raw/.")
    ap.add_argument("--project", default=None,
                    help="Only process rows with this project_hint (e.g. PROJ-0003).")
    ap.add_argument("--acq-id", default=None,
                    help="Only process this single ACQ-ID.")
    ap.add_argument("--apply", action="store_true",
                    help="Write changes. Default is a dry-run (touches nothing).")
    ap.add_argument("--force", action="store_true",
                    help="Re-derive even when anatomy is already set "
                         "(overwrites operator/prior anatomy — use with care).")
    args = ap.parse_args(argv)

    log(f"NAS root: {args.nas_root}")
    log(f"Mode: {'APPLY' if args.apply else 'DRY-RUN'}"
        f"{' +force' if args.force else ''}"
        f"{(' project=' + args.project) if args.project else ''}"
        f"{(' acq=' + args.acq_id) if args.acq_id else ''}")
    log("Anatomy mapping is a DRAFT (ingest/anatomy_derive.py) — review the "
        "filled regions before relying on them.", "WARN")

    counts = backfill(
        args.nas_root, project=args.project, acq_id=args.acq_id,
        apply=args.apply, force=args.force,
    )
    print()
    log(f"Summary: {counts}")
    verb = "filled" if args.apply else "would-fill"
    log(f"{counts[verb]} acquisition(s) {verb}; "
        f"{counts['no-derivation']} left null (no confident rule); "
        f"{counts['already-set']} already set.")
    return 1 if counts["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
