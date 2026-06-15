#!/usr/bin/env python3
"""backfill_microscopy_bestguess.py — LOW-CONFIDENCE best-guess enrichment for the
legacy Zeiss microscopy instruments with NO historical naming standard: Cell
Observer (CELL) and Confocal LSM 900 (LSM9).

These were the tissue-histology workhorses before the AxioScan 7, dumped into a
messy folder tree with no convention. We can only GUESS sample_type / anatomy from
words in the source path + filename. This tool scans each acquisition's
`original_name` (the full source relpath — ALREADY on the NAS, so it needs NO
access to the in-use source drive) against tools/reference/microscopy_bestguess_map.yaml
and proposes:
  - sample_type:  cells (a cell-line name appears) / tissue (an organ word appears,
                  no cell-line name) / "" unknown (neither — NEVER defaulted to cells)
  - anatomy.region: the UBERON organ, when tissue
  - condition.is_control: true when the name says ctrl/control/neg (best-guess)

Everything is written source="auto-guess" + a notes flag so the low confidence is
explicit and queryable. Safe-by-design, mirroring backfill_microscopy_anatomy.py:
  - DRY-RUN by default; --apply to write. Idempotent (only fills UNSET fields).
  - Atomic sidecar write (temp + os.replace) + verify; registry patched under lock.
  - Re-runnable: refine the YAML map and re-run to improve the guesses.

    python tools/backfill_microscopy_bestguess.py --nas-root J:/gjesus3-data            # dry-run
    python tools/backfill_microscopy_bestguess.py --nas-root J:/gjesus3-data --apply
"""
import argparse
import csv
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ingest import registry as reg, locking  # noqa: E402

MICRO_INSTRUMENTS = {"CELL", "LSM9"}
MAP_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "reference", "microscopy_bestguess_map.yaml")
_CTRL_RE = re.compile(r"(?<![a-z])(ctrl|control|neg(?:ativ)?)(?![a-z])", re.IGNORECASE)


def log(msg, level="INFO"):
    print(f"[bestguess] {level}: {msg}")


def load_map(path):
    import yaml
    with open(path, encoding="utf-8") as f:
        d = yaml.safe_load(f) or {}
    cells = [str(c).lower() for c in (d.get("cell_lines") or [])]
    organs = {str(k).lower(): v for k, v in (d.get("organs") or {}).items()}
    return cells, organs


def classify(relpath, cell_lines, organs):
    """relpath (folders + filename, case-insensitive) -> (sample_type, region|None).

    Precedence: cell-line fragment -> cells (wins); else organ word -> tissue+region;
    else ("", None) = unknown. Longest organ key wins on multiple hits.
    """
    text = (relpath or "").replace("\\", "/").lower()
    for frag in cell_lines:
        if frag in text:
            return "cells", None
    best = None
    for word, region in organs.items():
        if word in text:
            if best is None or len(word) > best[0]:
                best = (len(word), region)
    if best:
        return "tissue", best[1]
    return "", None


def guess_is_control(relpath):
    return bool(_CTRL_RE.search((relpath or "").replace("\\", "/")))


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def plan_one(sidecar, relpath, cell_lines, organs):
    """Return (changed_fields:dict, sample_type, region_label) — what we'd set.

    Only sets fields that are still UNSET, so it's idempotent. Returns ({}, ...)
    when there's nothing to do.
    """
    sample_type, region = classify(relpath, cell_lines, organs)
    is_ctrl = guess_is_control(relpath)
    changes = {}

    cur_type = (sidecar.get("user_supplied", {}).get("sample_type") or "").strip()
    if cur_type.upper() == "NA":
        cur_type = ""   # ingest-time placeholder counts as unset
    if sample_type and not cur_type:
        changes["sample_type"] = sample_type

    # anatomy (only for tissue, only if currently unset)
    if sample_type == "tissue" and region:
        anat = sidecar.get("anatomy")
        has_region = isinstance(anat, dict) and (anat.get("region") or {}).get("label")
        if not has_region:
            changes["anatomy_region"] = region

    # condition control-guess (only if currently unset)
    if is_ctrl:
        cond = sidecar.get("condition")
        cur = cond.get("is_control") if isinstance(cond, dict) else None
        if cur is None:
            changes["is_control"] = True

    return changes, sample_type, (region or {}).get("label") if region else None


def apply_changes(path, changes):
    sc = _read(path)
    if "sample_type" in changes:
        sc.setdefault("user_supplied", {})["sample_type"] = changes["sample_type"]
    if "anatomy_region" in changes:
        anat = sc.setdefault("anatomy", {})
        anat["is_whole_body"] = None
        anat["region"] = {"label": changes["anatomy_region"]["label"],
                          "ontology": "UBERON", "id": changes["anatomy_region"]["id"]}
        anat["source"] = "auto-guess"
        anat["auto_hint"] = "best-guess from source path/filename keyword (no naming standard)"
    if "is_control" in changes:
        cond = sc.setdefault("condition", {})
        cond["is_control"] = True
        cond["source"] = "auto-guess"
    _write(path, sc)
    # verify
    fresh = _read(path)
    if "sample_type" in changes and (fresh.get("user_supplied", {}).get("sample_type")
                                     != changes["sample_type"]):
        return False
    if "anatomy_region" in changes and ((fresh.get("anatomy", {}).get("region") or {}).get("label")
                                        != changes["anatomy_region"]["label"]):
        return False
    return True


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--nas-root", required=True)
    ap.add_argument("--project", default=None, help="limit to this project_hint")
    ap.add_argument("--instrument", default=None, choices=sorted(MICRO_INSTRUMENTS),
                    help="limit to CELL or LSM9")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)

    cell_lines, organs = load_map(MAP_PATH)
    registries_dir = os.path.join(args.nas_root, "registries")
    registry_path = os.path.join(registries_dir, "registry_raw.csv")
    rows = reg.read_registry(registry_path)

    counts = {"scanned": 0, "type-cells": 0, "type-tissue": 0, "type-unknown": 0,
              "anatomy-set": 0, "control-set": 0, "filled": 0, "would-fill": 0,
              "already-set": 0, "error": 0}
    reg_updates = {}  # acq_id -> {col: val}

    for row in rows:
        inst = (row.get("instrument") or "").strip()
        if inst not in MICRO_INSTRUMENTS:
            continue
        if args.instrument and inst != args.instrument:
            continue
        if args.project and (row.get("project_hint") or "") != args.project:
            continue
        aid = row.get("acq_id", "")
        relpath = row.get("original_name", "")
        acq_dir = os.path.normpath(os.path.join(args.nas_root,
                                                 (row.get("canonical_path") or "").lstrip("/")))
        path = os.path.join(acq_dir, "metadata.json")
        if not os.path.isfile(path):
            counts["error"] += 1
            log(f"{aid}: sidecar missing at {path}", "WARN")
            continue
        counts["scanned"] += 1
        try:
            sc = _read(path)
        except Exception as e:
            counts["error"] += 1
            log(f"{aid}: read failed: {e}", "ERROR")
            continue

        changes, stype, region_label = plan_one(sc, relpath, cell_lines, organs)
        counts["type-" + ("cells" if stype == "cells" else "tissue" if stype == "tissue" else "unknown")] += 1
        if not changes:
            counts["already-set"] += 1
            continue
        if not args.apply:
            counts["would-fill"] += 1
            log(f"{aid}: WOULD set {list(changes)} (type={stype or 'unknown'}"
                f"{', region=' + region_label if region_label else ''}) <- {relpath}")
            continue
        try:
            if apply_changes(path, changes):
                counts["filled"] += 1
                if "anatomy_region" in changes:
                    counts["anatomy-set"] += 1
                if "is_control" in changes:
                    counts["control-set"] += 1
                upd = {}
                if "sample_type" in changes:
                    upd["sample_type"] = changes["sample_type"]
                if "anatomy_region" in changes:
                    upd["anatomical_entity"] = changes["anatomy_region"]["label"]
                if upd:
                    reg_updates[aid] = upd
                log(f"{aid}: set {list(changes)} (type={stype or 'unknown'}"
                    f"{', region=' + region_label if region_label else ''})")
            else:
                counts["error"] += 1
                log(f"{aid}: verify-after-write FAILED", "ERROR")
        except Exception as e:
            counts["error"] += 1
            log(f"{aid}: apply failed: {e}", "ERROR")

    if args.apply and reg_updates:
        with locking.registry_lock(registries_dir):
            rows2 = reg.read_registry(registry_path)
            n = 0
            for r in rows2:
                u = reg_updates.get(r.get("acq_id"))
                if u:
                    for col, val in u.items():
                        if (r.get(col) or "") != val:
                            r[col] = val
                    n += 1
            tmp = registry_path + ".tmp"
            with open(tmp, "w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=reg.REGISTRY_FIELDS, extrasaction="ignore")
                w.writeheader()
                for r in rows2:
                    w.writerow({k: r.get(k, "") for k in reg.REGISTRY_FIELDS})
            os.replace(tmp, registry_path)
        log(f"registry: patched {n} row(s) (sample_type / anatomical_entity)")

    print()
    log(f"Summary: {counts}")
    return 1 if counts["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
