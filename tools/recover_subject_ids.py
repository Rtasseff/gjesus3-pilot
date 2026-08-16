#!/usr/bin/env python3
"""recover_subject_ids.py — ONE-SHOT repair of the `-AE-biomaGUNE-None` ids.

Rewrites ONE string field, `subject.facility_animal_id`, on the 444 production
acquisitions whose subject id was composed from a NULL facility project alias
(protocols 0219 / 0618 / 0619 / 1521). Audit:
tasks/SUBJECT_ID_NULL_ALIAS_HANDOFF.md. The composer is already fixed.

ONE-SHOT SCRIPT, NOT A TOOL — delete it once the repair is verified. It is
deliberately NOT modelled on recover_subject_metadata.py: there is no DB call
(the correct alias is `registry_raw.project_id` -> `registry_projects.name`,
already right on all 444 rows) and nothing to re-derive (each sidecar's
species / strain / sex / date_of_birth came from the DB under the correct
(project, animal) pair and is CORRECT — only the composed label broke).

Three writes, in order:

  1. `/raw/<acq>/metadata.json` — that one field. Atomic temp+replace and
     verify-after-write through recover_subject_metadata's own helpers.
     `checksums.json` is recomputed if it covers the sidecar; measured
     2026-08-14 it covers 0 of the 444, so that branch is a guard.
  2. `registries/registry_raw.csv` — line-oriented, in bytes; only the 444
     matched lines change. A csv round-trip would rewrite all 15,474.
  3. `registries/registry_subjects.csv` — DERIVED, so it is rebuilt from the
     now-correct sidecars via subjects_table.upsert_subjects and the stale
     `-None` rows dropped. The 3 collided ids split into 6 as a consequence
     of the upsert, not by hand.

Idempotent: a second --apply finds an empty worklist and changes 0 rows.

Usage:
    python tools/recover_subject_ids.py --nas-root J:\\gjesus3-data          # dry run
    python tools/recover_subject_ids.py --nas-root J:\\gjesus3-data --apply
"""

import argparse
import csv
import filecmp
import glob
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

from ingest import locking, subjects_table  # noqa: E402
from recover_subject_metadata import (  # noqa: E402  (reuse, don't re-implement)
    _read_sidecar, _verify_after_write, _write_sidecar)
from validate_registries import null_alias_of  # noqa: E402


def log(msg, level="INFO"):
    print(f"[{datetime.now():%H:%M:%S}] {level}: {msg}", file=sys.stderr)


def _rows(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def backup_registries(registries_dir, dest):
    """Copy every registry CSV off-NAS and REFUSE to continue unless each copy
    is byte-identical. Cheap insurance against the one irreversible step."""
    os.makedirs(dest, exist_ok=True)
    for src in sorted(glob.glob(os.path.join(registries_dir, "*.csv"))):
        dst = os.path.join(dest, os.path.basename(src))
        shutil.copy2(src, dst)
        if not filecmp.cmp(src, dst, shallow=False):
            raise RuntimeError(f"backup of {src} is NOT byte-identical - aborting")
        log(f"backed up {os.path.basename(src)} ({os.path.getsize(dst)} bytes, verified)")


def build_worklist(nas_root):
    """Every acquisition carrying a null-alias subject id -> a repair item.

    The correct alias comes from the project name and nothing else. A row whose
    project does not name an AE-biomaGUNE protocol is reported, never guessed.
    """
    registries = os.path.join(nas_root, "registries")
    projects = {p["project_id"].strip(): (p.get("name") or "").strip()
                for p in _rows(os.path.join(registries, "registry_projects.csv"))}
    work, unresolvable = [], []
    for r in _rows(os.path.join(registries, "registry_raw.csv")):
        old = (r.get("subject_ids") or "").strip()
        if null_alias_of(old) is None:
            continue
        name = projects.get((r.get("project_id") or "").strip(), "")
        if not name.startswith("AE-biomaGUNE-"):
            unresolvable.append((r["acq_id"], r.get("project_id"), name))
            continue
        folder = os.path.join(nas_root, *r["canonical_path"].strip("/").split("/"))
        work.append({
            "acq_id": r["acq_id"],
            "sidecar": os.path.join(folder, "metadata.json"),
            "checksums": os.path.join(folder, "checksums.json"),
            # The project NAME is already the id's tail: "AE-biomaGUNE-0219".
            # So the repair is the animal code re-joined to it.
            "old_id": old,
            "new_id": f"{old.split('-', 1)[0]}-{name}",
        })
    return work, unresolvable


def fix_sidecar(item, apply):
    """Rewrite subject.facility_animal_id. Returns the corrected subject block."""
    md = _read_sidecar(item["sidecar"])
    subject = md.get("subject")
    if not isinstance(subject, dict):
        raise RuntimeError(f"{item['acq_id']}: sidecar has no subject: block")
    current = subject.get("facility_animal_id")
    # Already carrying the right id: an earlier run wrote the sidecars and then
    # died before the registry (they are written outside the lock, the registry
    # inside it). That is the RESUME case, not a mismatch - treating it as one
    # would abort every retry at pre-flight and strand the repair half-done.
    if current == item["new_id"]:
        item["already"] = True
        return subject
    if current != item["old_id"]:
        raise RuntimeError(
            f"{item['acq_id']}: sidecar id {current!r} != registry id "
            f"{item['old_id']!r} - refusing to guess")
    subject["facility_animal_id"] = item["new_id"]
    if apply:
        _write_sidecar(item["sidecar"], md)
        ok, detail = _verify_after_write(
            item["sidecar"], {"facility_animal_id": item["new_id"]})
        if not ok:
            raise RuntimeError(f"{item['acq_id']}: verify-after-write failed: {detail}")
        _refresh_checksum(item)
    return subject


def _refresh_checksum(item):
    """Recompute the sidecar's checksums.json entry IF it is covered by one.

    0 of 444 on 2026-08-14 - but silently invalidating a fixity record is the
    kind of thing found years later, so check rather than assume.
    """
    if not os.path.isfile(item["checksums"]):
        return
    with open(item["checksums"], "r", encoding="utf-8") as f:
        doc = json.load(f)
    files = doc.get("files") if isinstance(doc, dict) else None
    if not isinstance(files, dict):
        return
    key = next((k for k in files if k.endswith("metadata.json")), None)
    if key is None:
        return
    with open(item["sidecar"], "rb") as f:
        files[key] = hashlib.sha256(f.read()).hexdigest()
    tmp = item["checksums"] + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, item["checksums"])
    log(f"{item['acq_id']}: checksums.json entry for the sidecar recomputed")


def fix_registry_raw(path, work):
    """Line-oriented, single pass, in BYTES. Returns the number of lines changed.

    Bytes and no codec on the way through: the live file has NO BOM and CRLF
    endings (checked 2026-08-14), so a utf-8-sig round-trip would ADD a BOM to
    8 MB of registry and text mode would rewrite every terminator. Here only
    the matched lines change; the other 15,030 survive byte-for-byte.

    Refuses a line where the old id is not present exactly once, rather than
    doing a fuzzy replace on a production registry.
    """
    by_acq = {i["acq_id"]: i for i in work}
    with open(path, "rb") as f:
        lines = f.readlines()
    changed = 0
    for n, line in enumerate(lines):
        item = by_acq.get(line.split(b",", 1)[0].decode("utf-8", "replace"))
        if item is None:
            continue
        old, new = item["old_id"].encode(), item["new_id"].encode()
        if line.count(old) != 1:
            raise RuntimeError(
                f"{item['acq_id']}: old id appears {line.count(old)}x on its "
                f"line - refusing a fuzzy replace")
        lines[n] = line.replace(old, new)
        changed += 1
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "wb") as f:
        f.writelines(lines)
    os.replace(tmp, path)
    return changed


def fix_subjects(registries_dir, blocks):
    """Upsert the corrected blocks, then drop the stale -None rows.

    Derived from the sidecars, never edited in place: the 3 collided ids split
    into 6 because 6 distinct corrected ids get upserted, not because anything
    here knows about collisions.
    """
    path = subjects_table.subjects_path(registries_dir)
    rows = [r for r in (subjects_table.row_from_subject_block(b) for b in blocks) if r]
    stats = subjects_table.upsert_subjects(registries_dir, rows, log=log,
                                           _hold_lock=False)
    table = subjects_table.read_subjects(path)
    stale = [k for k in table if null_alias_of(k) is not None]
    for k in stale:
        del table[k]
    if stale:
        subjects_table.write_subjects(path, table)
    return stats, len(stale), len(table)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--nas-root", default=os.environ.get("GJESUS3_ROOT", "/mnt/gjesus3"))
    p.add_argument("--backup-dir", default=os.path.join(
        os.path.expanduser("~"), "temp",
        f"gjesus3_subject_id_fix_{datetime.now():%Y%m%d}"))
    p.add_argument("--apply", action="store_true",
                   help="actually write (default: dry run, touches nothing)")
    args = p.parse_args(argv)

    registries = os.path.join(args.nas_root, "registries")
    if not os.path.isdir(registries):
        log(f"no registries/ under {args.nas_root!r}", "ERROR")
        return 2

    work, unresolvable = build_worklist(args.nas_root)
    for acq, pid, name in unresolvable:
        log(f"{acq}: project {pid} ({name!r}) is not an AE-biomaGUNE protocol - "
            f"SKIPPED, repair by hand", "ERROR")
    log(f"worklist: {len(work)} acquisition(s), "
        f"{len({i['old_id'] for i in work})} distinct broken id(s) -> "
        f"{len({i['new_id'] for i in work})} distinct correct id(s)")
    if not work:
        log("nothing to do.")
        return 1 if unresolvable else 0
    for i in work[:5]:
        log(f"  {i['acq_id']}: {i['old_id']} -> {i['new_id']}")
    if len(work) > 5:
        log(f"  ... and {len(work) - 5} more")

    # Pre-flight: read every sidecar and cross-check its id against the
    # registry's. Raises BEFORE anything is written if the two ever disagree.
    blocks = [fix_sidecar(i, apply=False) for i in work]
    resumed = sum(1 for i in work if i.get("already"))
    log(f"{len(blocks)} sidecar(s) cross-checked against the registry"
        + (f"; {resumed} already repaired by an earlier interrupted run "
           f"(their registry rows are not)" if resumed else ""))

    if not args.apply:
        log("DRY RUN - nothing written. Re-run with --apply.")
        return 0

    backup_registries(registries, args.backup_dir)

    # Sidecars first: the subjects table is rebuilt FROM them, and /raw/ is the
    # record. Outside the lock - these are 444 independent files, and the lock
    # must never be held across a long file walk.
    blocks = [fix_sidecar(i, apply=True) for i in work]
    log(f"{len(blocks) - resumed} sidecar(s) rewritten + verified"
        + (f", {resumed} already correct and left alone" if resumed else ""))

    with locking.registry_lock(registries, log=log):
        changed = fix_registry_raw(
            os.path.join(registries, "registry_raw.csv"), work)
        log(f"registry_raw.csv: {changed} line(s) rewritten")
        stats, dropped, total = fix_subjects(registries, blocks)
        log(f"registry_subjects.csv: {stats['inserted']} inserted, "
            f"{stats['updated']} updated, {dropped} stale -None row(s) dropped, "
            f"{total} rows total")

    if changed != len(work):
        log(f"registry_raw changed {changed} lines but the worklist had "
            f"{len(work)} - INVESTIGATE", "ERROR")
        return 1
    log("done. Verify with validate_registries.py (expect 0 errors).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
