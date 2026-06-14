#!/usr/bin/env python3
"""backfill_microscopy_anatomy.py — back-fill anatomy on already-ingested
microscopy (AxioScan etc.) acquisitions from the sample-id organ code.

Sibling to tools/backfill_mri_anatomy.py — same controlled-update shape, but the
anatomy signal is the microscopy **sample-id organ code** (operator-keyed),
mapped via tools/reference/microscopy_organ_map.yaml (the SAME map the live
ingest auto-derives with — single source of truth). The ingest had been
discarding the organ (enrichment.py parsed `_organ` and dropped it), so existing
AxioScan acqs landed `anatomy.region = null` even though the organ is in the name.

Safe-by-design (mirrors recover_subject_metadata.py / backfill_mri_anatomy.py):
  - DRY-RUN by default (touches nothing); pass --apply to write.
  - Only fills acqs whose anatomy is still UNSET; operator-entered anatomy is
    never overwritten (use --force to re-derive).
  - High-confidence only: an unmapped/ambiguous organ code is left null.
  - Atomic sidecar write + verify-after-write + rollback; registry
    `anatomical_entity` patched under the registry lock.

Run (dry-run preview):
    PYTHONPATH=tools python tools/backfill_microscopy_anatomy.py --nas-root J:/gjesus3-data
Apply:
    PYTHONPATH=tools python tools/backfill_microscopy_anatomy.py --nas-root J:/gjesus3-data --apply
"""

import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ on path

from ingest import anatomy_derive, registry as reg, locking  # noqa: E402


def log(msg, level="INFO"):
    print(f"[backfill-microscopy-anatomy] {level}: {msg}")


def _read_sidecar(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_sidecar(path, sidecar):
    """Atomic sidecar write (temp + os.replace), preserving 2-space indent + \\n.
    The /raw sidecar is immutable-by-policy, so the write must never leave a
    truncated file."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(sidecar, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def _sidecar_path(nas_root, canonical_path):
    rel = (canonical_path or "").lstrip("/")
    return os.path.normpath(os.path.join(nas_root, rel, "metadata.json"))


def _anatomy_is_unset(anatomy):
    """True if the anatomy block has no region label AND is_whole_body is null."""
    region = anatomy.get("region") or {}
    has_region = bool(isinstance(region, dict) and region.get("label"))
    return (not has_region) and anatomy.get("is_whole_body") is None


def _sample_short(sidecar, row):
    """Best source for the sample-id chunk: the sidecar's discovered.sample_short
    (clean, e.g. 'ID12Lu' / 'mPCLS_n1'), falling back to the registry sample_id's
    last '_'-segment."""
    short = ((sidecar.get("discovered") or {}).get("sample_short") or "").strip()
    if short:
        return short
    sid = (row.get("sample_id") or "").strip()
    return sid.rsplit("_", 1)[-1] if sid else ""


def plan_one(sidecar, sample_short, operator, *, force=False, organ_map=None):
    """Decide whether/what to back-fill for one microscopy sidecar.

    Returns (outcome, proposed): no-anatomy | already-set | no-derivation | fill.
    """
    anatomy = sidecar.get("anatomy")
    if not isinstance(anatomy, dict):
        return "no-anatomy", None
    if not force and not _anatomy_is_unset(anatomy):
        return "already-set", None
    proposed = anatomy_derive.derive_microscopy_anatomy(
        sample_short, operator, organ_map=organ_map,
    )
    if not proposed:
        return "no-derivation", None
    return "fill", proposed


def _apply_to_sidecar(path, proposed):
    """Write the proposed anatomy fields (incl. additional_regions) into the
    sidecar; verify; rollback on failure. Returns (ok, detail)."""
    try:
        sidecar = _read_sidecar(path)
    except Exception as e:
        return False, f"re-read failed: {e}"
    anatomy = sidecar.get("anatomy")
    if not isinstance(anatomy, dict):
        return False, "anatomy block vanished"
    backup = dict(anatomy)
    anatomy["region"] = proposed["region"]
    if proposed.get("additional_regions"):
        anatomy["additional_regions"] = proposed["additional_regions"]
    anatomy["auto_hint"] = proposed["auto_hint"]
    anatomy["source"] = proposed["source"]
    try:
        _write_sidecar(path, sidecar)
    except Exception as e:
        return False, f"write failed: {e}"
    try:
        fresh = _read_sidecar(path).get("anatomy") or {}
    except Exception as e:
        return False, f"verify re-read failed: {e}"
    if (fresh.get("region") or {}).get("label") != proposed["region"]["label"]:
        sidecar["anatomy"] = backup
        try:
            _write_sidecar(path, sidecar)
        except Exception:
            pass
        return False, "verify-after-write FAILED; rolled back"
    return True, "filled + verified"


def _update_registry(registry_path, registries_dir, updates):
    """Patch the `anatomical_entity` cell for each {acq_id: label} under the
    registry lock; rewrite the CSV atomically. Returns rows changed."""
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


def backfill(nas_root, *, project=None, acq_id=None, apply=False, force=False,
             organ_map=None):
    """Walk the registry, back-fill anatomy on unset MICROSCOPY acquisitions."""
    registries_dir = os.path.join(nas_root, "registries")
    registry_path = os.path.join(registries_dir, "registry_raw.csv")
    rows = reg.read_registry(registry_path)
    if organ_map is None:
        organ_map = anatomy_derive.load_organ_map()
    counts = {"scanned": 0, "filled": 0, "would-fill": 0, "already-set": 0,
              "no-derivation": 0, "no-anatomy": 0, "not-microscopy": 0,
              "missing-sidecar": 0, "error": 0}
    by_region = {}
    registry_updates = {}

    for row in rows:
        aid = row.get("acq_id", "")
        if acq_id and aid != acq_id:
            continue
        if project and (row.get("project_hint") or "") != project:
            continue
        if (row.get("data_ecosystem") or "").upper() != "MICROSCOPY":
            counts["not-microscopy"] += 1
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

        short = _sample_short(sidecar, row)
        operator = row.get("operator", "")
        outcome, proposed = plan_one(sidecar, short, operator,
                                     force=force, organ_map=organ_map)
        if outcome in ("no-anatomy", "already-set", "no-derivation"):
            counts[outcome] += 1
            continue

        label = proposed["region"]["label"]
        by_region[label] = by_region.get(label, 0) + 1
        if not apply:
            counts["would-fill"] += 1
            extra = (" +" + ",".join(r["label"] for r in proposed["additional_regions"])
                     if proposed.get("additional_regions") else "")
            log(f"{aid}: WOULD fill region={label}{extra} "
                f"(operator={operator}, sample={short})")
            continue
        ok, detail = _apply_to_sidecar(path, proposed)
        if ok:
            counts["filled"] += 1
            registry_updates[aid] = label
            log(f"{aid}: filled region={label} (sample={short}; {detail})")
        else:
            counts["error"] += 1
            log(f"{aid}: {detail}", "ERROR")

    if apply and registry_updates:
        n = _update_registry(registry_path, registries_dir, registry_updates)
        log(f"registry: patched anatomical_entity on {n} row(s)")

    counts["by_region"] = by_region
    return counts


def main(argv=None):
    ap = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--nas-root", required=True,
                    help="NAS root (e.g. J:/gjesus3-data) holding registries/ + raw/.")
    ap.add_argument("--project", default=None,
                    help="Only process rows with this project_hint.")
    ap.add_argument("--acq-id", default=None, help="Only process this single ACQ-ID.")
    ap.add_argument("--apply", action="store_true",
                    help="Write changes. Default is a dry-run (touches nothing).")
    ap.add_argument("--force", action="store_true",
                    help="Re-derive even when anatomy is already set (use with care).")
    ap.add_argument("--organ-map", default=None,
                    help="Path to the organ map YAML (default: "
                         "tools/reference/microscopy_organ_map.yaml).")
    args = ap.parse_args(argv)

    organ_map = anatomy_derive.load_organ_map(args.organ_map)
    if not organ_map:
        log("organ map is empty or not found — nothing will derive. Check "
            "tools/reference/microscopy_organ_map.yaml.", "WARN")

    log(f"NAS root: {args.nas_root}")
    log(f"Mode: {'APPLY' if args.apply else 'DRY-RUN'}"
        f"{' +force' if args.force else ''}"
        f"{(' project=' + args.project) if args.project else ''}"
        f"{(' acq=' + args.acq_id) if args.acq_id else ''}")
    log(f"Organ map operators: {sorted(organ_map.keys())}")

    counts = backfill(args.nas_root, project=args.project, acq_id=args.acq_id,
                      apply=args.apply, force=args.force, organ_map=organ_map)
    print()
    log(f"Summary: {counts}")
    verb = "filled" if args.apply else "would-fill"
    log(f"{counts[verb]} acquisition(s) {verb} (by region: {counts.get('by_region', {})}); "
        f"{counts['no-derivation']} left null (unmapped/ambiguous organ code); "
        f"{counts['already-set']} already set.")
    return 1 if counts["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
