#!/usr/bin/env python3
"""backfill_sidecar_condition.py — fill the `condition` block (and add missing
`user_provided_metadata` tables) on already-ingested acquisitions, per case.

Context (2026-11-07): the CNIC-HEARDS collaborator batches were ingested with no
`condition:` block, so every sidecar says `is_control: null`, although the
collaborator's own folders say which series are the healthy baseline and which
the induced ARDS. (The ingest can set it per case since 2026-11-07; batches
ingested before, or without a `condition:` block, cannot.) This tool fills it
afterwards, the same way the other recovery tools do
(tools/recover_subject_metadata.py).

Inputs (both are back-fill inputs, kept outside the code):
  --config  a YAML with the same `condition:` and `user_metadata:` blocks an
            ingest config takes. Values may be `${discovered.<column>}`,
            is_control and timepoint_days included.
  --table   a CSV with an `acq_id` column plus the columns the config refers
            to. One row per acquisition to fill; acquisitions not listed are
            never touched.

The condition block is built with the ingest's own resolver
(ingest/resolver.resolve_condition_block) and the tables with the ingest's own
reader (ingest/user_tables.build_user_metadata), so a filled sidecar reads
exactly as if the ingest had been given the block.

Safe-by-design, mirroring tools/backfill_mri_anatomy.py:
  - DRY-RUN by default (touches nothing); pass --apply to write.
  - condition: fills only a block that is still UNSET (is_control null, every
    text field empty, source 'unknown'). A set block is never overwritten.
  - user_provided_metadata: adds a table label only when that label is absent.
    Existing labels are never overwritten.
  - --apply needs --backup-dir: each sidecar is copied there before its write.
  - Atomic sidecar write + verify-after-write + rollback on failure.
  - Sidecars only. The registry has no condition column; nothing else changes.

Run (dry-run):
    python tools/backfill_sidecar_condition.py --nas-root J:/gjesus3-data \
        --config <backfill.yaml> --table <cases.csv>
Apply:
    ... --apply --backup-dir <folder>
"""

import argparse
import csv
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # tools/ on path

from ingest import registry as reg, resolver, user_tables  # noqa: E402

TEXT_FIELDS = ("disease_model", "disease_state", "control_type", "study_arm")


def log(msg, level="INFO"):
    print(f"[backfill-condition] {level}: {msg}")


def _read_sidecar(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_sidecar(path, sidecar):
    """Atomic sidecar write (temp + os.replace), 2-space indent + trailing
    newline as elsewhere; never leaves a truncated file."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(sidecar, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def _sidecar_path(nas_root, canonical_path):
    rel = (canonical_path or "").lstrip("/")
    return os.path.normpath(os.path.join(nas_root, rel, "metadata.json"))


def condition_is_unset(cond):
    """True if the condition block carries nothing: the ingest default."""
    if not isinstance(cond, dict):
        return True
    return (cond.get("is_control") is None
            and not any(cond.get(k) for k in TEXT_FIELDS)
            and cond.get("treatment") in (None, "")
            and cond.get("timepoint_days") is None
            and cond.get("source") in (None, "", "unknown"))


def resolve_condition(block, row):
    """The ingest's own resolve_condition_block (per-case values included)."""
    if not block:
        return None
    return resolver.resolve_condition_block(block, row)


def plan_one(sidecar, row, cfg):
    """Return (changes, notes). changes: {"condition": dict} and/or
    {"user_provided_metadata": {label: block}} — only what is to be written."""
    changes, notes = {}, []
    proposed = resolve_condition(cfg.get("condition"), row)
    if proposed is not None:
        if "condition" not in sidecar:
            notes.append("no condition block in this sidecar (not organism/tissue): skipped")
        elif not condition_is_unset(sidecar.get("condition")):
            notes.append("condition already set: kept")
        elif proposed.get("is_control") is None and not any(proposed.get(k) for k in TEXT_FIELDS):
            notes.append("nothing to fill for condition (table row empty)")
        else:
            changes["condition"] = proposed
    um = user_tables.build_user_metadata(cfg.get("user_metadata"), row,
                                         log=lambda m, lvl="INFO": notes.append(f"{lvl}: {m}"))
    if um:
        have = sidecar.get("user_provided_metadata") or {}
        add = {label: blk for label, blk in um.items() if label not in have}
        for label in um:
            if label in have:
                notes.append(f"user_provided_metadata.{label} already present: kept")
        if add:
            changes["user_provided_metadata"] = add
    return changes, notes


def apply_one(path, changes, backup_dir, acq_id):
    """Back up, write, verify; roll back on a failed verify. Returns (ok, detail)."""
    try:
        sidecar = _read_sidecar(path)
    except Exception as e:
        return False, f"re-read failed: {e}"
    os.makedirs(backup_dir, exist_ok=True)
    backup = os.path.join(backup_dir, f"{acq_id}.metadata.json")
    if os.path.exists(backup):
        return False, f"backup already exists ({backup}); refusing to overwrite it"
    shutil.copy2(path, backup)
    before = json.loads(json.dumps(sidecar))
    if "condition" in changes:
        sidecar["condition"] = changes["condition"]
    if "user_provided_metadata" in changes:
        upm = sidecar.get("user_provided_metadata") or {}
        upm.update(changes["user_provided_metadata"])
        sidecar["user_provided_metadata"] = upm
    try:
        _write_sidecar(path, sidecar)
    except Exception as e:
        return False, f"write failed: {e}"
    try:
        fresh = _read_sidecar(path)
    except Exception as e:
        fresh = None
        err = f"verify re-read failed: {e}"
    ok = fresh is not None
    if ok and "condition" in changes:
        ok = fresh.get("condition") == changes["condition"]
    if ok and "user_provided_metadata" in changes:
        ok = all((fresh.get("user_provided_metadata") or {}).get(k) == v
                 for k, v in changes["user_provided_metadata"].items())
    if ok:
        # Everything outside the changed blocks must be untouched.
        rest = {k: v for k, v in fresh.items() if k not in changes}
        ok = rest == {k: v for k, v in before.items() if k not in changes}
    if not ok:
        _write_sidecar(path, before)
        return False, "verify-after-write FAILED; rolled back" if fresh is not None else err
    return True, f"filled + verified (backup {os.path.basename(backup)})"


def backfill(nas_root, cfg, table_rows, *, apply=False, backup_dir=None):
    rows = reg.read_registry(os.path.join(nas_root, "registries", "registry_raw.csv"))
    by_id = {r["acq_id"]: r for r in rows}
    counts = {"listed": len(table_rows), "would-change": 0, "changed": 0,
              "nothing-to-do": 0, "not-in-registry": 0, "missing-sidecar": 0, "error": 0,
              "condition": 0, "user_provided_metadata": 0}
    report = []
    for row in table_rows:
        aid = row.get("acq_id", "")
        reg_row = by_id.get(aid)
        if not reg_row:
            counts["not-in-registry"] += 1
            log(f"{aid}: not in registry_raw.csv", "ERROR")
            continue
        path = _sidecar_path(nas_root, reg_row.get("canonical_path", ""))
        if not os.path.isfile(path):
            counts["missing-sidecar"] += 1
            log(f"{aid}: sidecar not found at {path}", "ERROR")
            continue
        try:
            sidecar = _read_sidecar(path)
        except Exception as e:
            counts["error"] += 1
            log(f"{aid}: could not read sidecar: {e}", "ERROR")
            continue
        changes, notes = plan_one(sidecar, row, cfg)
        for n in notes:
            log(f"{aid}: {n}")
        if not changes:
            counts["nothing-to-do"] += 1
            continue
        for k in changes:
            counts[k] += 1
        what = ", ".join(
            ([f"condition(is_control={changes['condition']['is_control']}, "
              f"disease_state={changes['condition']['disease_state']!r})"] if "condition" in changes else [])
            + [f"user_provided_metadata.{lbl}" for lbl in changes.get("user_provided_metadata", {})])
        report.append({"acq_id": aid, "original_name": reg_row.get("original_name", ""), "changes": what})
        if not apply:
            counts["would-change"] += 1
            log(f"{aid} ({reg_row.get('original_name', '')}): WOULD write {what}")
            continue
        ok, detail = apply_one(path, changes, backup_dir, aid)
        if ok:
            counts["changed"] += 1
            log(f"{aid}: wrote {what}; {detail}")
        else:
            counts["error"] += 1
            log(f"{aid}: {detail}", "ERROR")
    return counts, report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--nas-root", required=True, help="NAS root holding registries/ + raw/.")
    ap.add_argument("--config", required=True, help="YAML with condition: and/or user_metadata: blocks.")
    ap.add_argument("--table", required=True, help="CSV with acq_id + the columns the config refers to.")
    ap.add_argument("--apply", action="store_true", help="Write. Default is a dry-run.")
    ap.add_argument("--backup-dir", default=None, help="Required with --apply: sidecar copies before writing.")
    ap.add_argument("--report", default=None, help="Optional CSV of what was (or would be) written.")
    args = ap.parse_args(argv)
    if args.apply and not args.backup_dir:
        ap.error("--apply needs --backup-dir")

    import yaml
    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    errs = resolver.validate_condition_block(cfg.get("condition"))
    errs +=user_tables.validate_user_metadata_block(cfg.get("user_metadata"))
    if errs:
        for e in errs:
            log(e, "ERROR")
        return 2
    with open(args.table, encoding="utf-8", newline="") as f:
        table_rows = list(csv.DictReader(f))
    ids = [r.get("acq_id", "") for r in table_rows]
    if len(ids) != len(set(ids)) or not all(ids):
        log("table: acq_id must be present and unique on every row", "ERROR")
        return 2

    log(f"NAS root: {args.nas_root}; Mode: {'APPLY' if args.apply else 'DRY-RUN'}; "
        f"{len(table_rows)} acquisition(s) listed")
    counts, report = backfill(args.nas_root, cfg, table_rows, apply=args.apply, backup_dir=args.backup_dir)
    if args.report and report:
        with open(args.report, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["acq_id", "original_name", "changes"])
            w.writeheader()
            w.writerows(report)
    print()
    log(f"Summary: {counts}")
    return 1 if (counts["error"] or counts["not-in-registry"] or counts["missing-sidecar"]) else 0


if __name__ == "__main__":
    sys.exit(main())
