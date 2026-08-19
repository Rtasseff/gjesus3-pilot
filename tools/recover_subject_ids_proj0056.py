#!/usr/bin/env python3
"""recover_subject_ids_proj0056.py — ONE-SHOT repair of the PROJ-0056 `rN` subject ids.

15 acquisitions from the 2023-10-26/27 PROJ-0056 rat sessions carry subject ids
composed from a RECONSTRUCTION folder, not an animal. The researcher's tree is
`<protocol>/<yymmdd>/<animal_code>/r<N>/` — `r1`/`r2`/`r3` are reconstructions of
one scan (identical acquisition timestamps, `OSEM_1/2/3`). The ingest recipe read
the `rN` level as the subject, so `r1` -> animal code `1` -> `1-AE-biomaGUNE-0421`.

Those ids RESOLVED: animals 1/2/3 of protocol 0421 are real rats born 2021-07-08
whose only logged procedure is a tail-vein injection on 2021-09-08. So the whole
`subject:` block is wrong — species/strain/sex happen to match the cohort, but
date_of_birth, age_at_acquisition and procedures belong to three uninvolved
animals two years older. This is why the block is REBUILT from the facility DB
rather than relabelled (contrast recover_subject_ids.py, where only the composed
label had broken and the biology underneath was already correct).

EVIDENCE for the corrected attribution — three independent sources agree:
  1. the researcher's own folder above `rN` (`.../231026/230/r1/...`), recorded
     verbatim in each sidecar as `discovered.series` + `source_relpath`;
  2. the animal-facility DB, which logs `Admin RT +Pet` AND `CT` for 230 and 231
     on exactly 2023-10-26, and for 236 and 237 on exactly 2023-10-27;
  3. the DICOM PatientID, which reads 230 / 231 / 237 on 11 of the 15.

The remaining 4 (`ACQ-20231027-PET-001/002/003` + `ACQ-20231027-CT-001`, folder
236) carry a CONTRADICTORY console PatientID: `234` on the PETs and the free-text
`237_234PETes237` on the CT — an operator correction note typed into the ID field.
They are repaired to 236 under the same rule as the other 11, because 236 is what
makes both records consistent: the DB logs a PET and a CT for 236 that day and
NONE for 234 ever, and 234 appears nowhere else in the registry. The console
disagreement is deliberately NOT erased — `discovered.series`, the source path and
the DICOM header all survive untouched, so the evidence stays re-derivable.

Only the `subject:` block is rewritten. The whole `discovered:` block is left as
the record of what the parser actually did, INCLUDING the now-stale
`discovered.animal_codes: "1"`. That is safe: `animal_codes` is an ingest-time
intermediate (written by ingest/config.py, consumed by ingest/enrichment.py in the
same run) and nothing re-reads it from a sidecar afterwards —
recover_subject_metadata.py re-derives from `facility_animal_id`, which is now
correct, so a later recovery pass over these 15 resolves the RIGHT animal.

Three writes, in order (mirroring recover_subject_ids.py, which was reviewed and
run against production 2026-08-16):

  1. `/raw/<acq>/metadata.json` — the whole `subject:` block, rebuilt from the DB
     via enrichment._finalize_subject so field order and sentinels match
     08_METADATA §4.4.2 exactly. Atomic temp+replace, verified after write, each
     file's existing line terminator preserved.
  2. `registries/registry_raw.csv` — line-oriented, in BYTES (no BOM + CRLF live);
     the comma-delimited field is matched so no substring can collide.
  3. `registries/registry_subjects.csv` — DERIVED, rebuilt from the corrected
     sidecars via subjects_table.upsert_subjects; the 3 now-unreferenced `rN` rows
     are dropped only after asserting nothing still points at them.

Idempotent: a second --apply finds an empty worklist and changes 0 rows.

Usage:
    python tools/recover_subject_ids_proj0056.py --nas-root J:\\gjesus3-data
    python tools/recover_subject_ids_proj0056.py --nas-root J:\\gjesus3-data --apply
"""

import argparse
import csv
import filecmp
import glob
import os
import re
import shutil
import sys
from datetime import datetime

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import animal_db  # noqa: E402
from ingest import enrichment, locking, subjects_table  # noqa: E402
from recover_subject_metadata import (  # noqa: E402  (reuse, don't re-implement)
    _read_sidecar, _verify_after_write, _write_sidecar)

RECON_SUBJECT_RE = re.compile(r"^r\d+$")


def log(msg, level="INFO"):
    print(f"[{datetime.now():%H:%M:%S}] {level}: {msg}", file=sys.stderr)


def _rows(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def backup_registries(registries_dir, dest):
    """Copy every registry CSV off-NAS, byte-identical or abort."""
    os.makedirs(dest, exist_ok=True)
    for src in sorted(glob.glob(os.path.join(registries_dir, "*.csv"))):
        dst = os.path.join(dest, os.path.basename(src))
        shutil.copy2(src, dst)
        if not filecmp.cmp(src, dst, shallow=False):
            raise RuntimeError(f"backup of {src} is NOT byte-identical - aborting")
        log(f"backed up {os.path.basename(src)} ({os.path.getsize(dst)} bytes, verified)")


def build_worklist(nas_root):
    """Acquisitions whose subject token is a reconstruction folder, not an animal.

    Self-limiting: the `rN` shape IS the defect signature. It is read from the
    registry's `sample_id` FIRST so only the handful of candidate sidecars are
    opened — walking all 15k over SMB to find 15 rows takes minutes. The sidecar
    still has the last word: it must agree, and it carries the animal code.
    An acquisition without a numeric `discovered.series` is reported, never guessed.
    """
    registries = os.path.join(nas_root, "registries")
    projects = {p["project_id"].strip(): (p.get("name") or "").strip()
                for p in _rows(os.path.join(registries, "registry_projects.csv"))}
    work, unresolvable = [], []
    for r in _rows(os.path.join(registries, "registry_raw.csv")):
        if not RECON_SUBJECT_RE.match((r.get("sample_id") or "").strip()):
            continue
        folder = os.path.join(nas_root, *r["canonical_path"].strip("/").split("/"))
        sidecar = os.path.join(folder, "metadata.json")
        if not os.path.isfile(sidecar):
            unresolvable.append((r["acq_id"], "", "no sidecar on disk"))
            continue
        disc = (_read_sidecar(sidecar) or {}).get("discovered") or {}
        if not RECON_SUBJECT_RE.match(str(disc.get("subject", ""))):
            unresolvable.append((r["acq_id"], str(disc.get("subject", "")),
                                 "sidecar subject disagrees with sample_id"))
            continue
        code = str(disc.get("series", "")).strip()
        name = projects.get((r.get("project_id") or "").strip(), "")
        if not code.isdigit() or not name.startswith("AE-biomaGUNE-"):
            unresolvable.append((r["acq_id"], code, name))
            continue
        work.append({
            "acq_id": r["acq_id"],
            "sidecar": sidecar,
            "old_id": (r.get("subject_ids") or "").strip(),
            "new_id": f"{code}-{name}",
            "alias": name.rsplit("-", 1)[-1],
            "code": code,
            "acq_dt": r.get("acquisition_datetime") or "",
        })
    return work, unresolvable


def _corrected_block(item, existing):
    """Rebuild the subject block from the facility DB for the RIGHT animal."""
    res = animal_db.lookup(item["alias"], int(item["code"]))
    if res.status != "found":
        raise RuntimeError(
            f"{item['acq_id']}: facility DB has no animal {item['code']} in "
            f"protocol {item['alias']} ({res.status}/{res.reason}) - refusing "
            f"to invent a subject")
    block = enrichment._finalize_subject(
        dict(res.subject), item["acq_dt"], "animal-facility-db")
    if block["facility_animal_id"] != item["new_id"]:
        raise RuntimeError(
            f"{item['acq_id']}: DB composed {block['facility_animal_id']!r}, "
            f"expected {item['new_id']!r}")
    # The DB never supplies weight; keep whatever the operator/instrument gave.
    if existing.get("weight_at_acquisition_g") is not None:
        block["weight_at_acquisition_g"] = existing["weight_at_acquisition_g"]
    return block


def fix_sidecar(item, apply):
    """Replace the subject block. Returns the corrected block."""
    md = _read_sidecar(item["sidecar"])
    subject = md.get("subject")
    if not isinstance(subject, dict):
        raise RuntimeError(f"{item['acq_id']}: sidecar has no subject: block")
    current = subject.get("facility_animal_id")
    # Already correct: an earlier run wrote the sidecars (outside the lock) and
    # died before the registry (inside it). Resume, do not abort.
    if current == item["new_id"]:
        item["already"] = True
        return subject
    if current != item["old_id"]:
        raise RuntimeError(
            f"{item['acq_id']}: sidecar id {current!r} != registry id "
            f"{item['old_id']!r} - refusing to guess")
    block = _corrected_block(item, subject)
    md["subject"] = block
    if apply:
        _write_sidecar(item["sidecar"], md)
        ok, detail = _verify_after_write(
            item["sidecar"], {"facility_animal_id": item["new_id"]})
        if not ok:
            raise RuntimeError(f"{item['acq_id']}: verify-after-write failed: {detail}")
    return block


def fix_registry_raw(path, work):
    """Line-oriented, single pass, in BYTES. Returns lines changed.

    The live file has NO BOM and CRLF endings, so a utf-8-sig round-trip would
    ADD a BOM to 8 MB of registry and text mode would rewrite every terminator.
    The COMMA-DELIMITED field is matched, so `1-AE-biomaGUNE-0421` can never hit
    inside `231-AE-biomaGUNE-0421`.
    """
    by_acq = {i["acq_id"]: i for i in work}
    with open(path, "rb") as f:
        lines = f.readlines()
    changed = 0
    for n, line in enumerate(lines):
        item = by_acq.get(line.split(b",", 1)[0].decode("utf-8", "replace"))
        if item is None:
            continue
        old = b"," + item["old_id"].encode() + b","
        new = b"," + item["new_id"].encode() + b","
        if line.count(old) != 1:
            raise RuntimeError(
                f"{item['acq_id']}: delimited old id appears {line.count(old)}x "
                f"on its line - refusing a fuzzy replace")
        lines[n] = line.replace(old, new)
        changed += 1
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "wb") as f:
        f.writelines(lines)
    os.replace(tmp, path)
    return changed


def fix_subjects(registries_dir, blocks, work):
    """Upsert the corrected blocks, then drop old ids IF nothing references them."""
    path = subjects_table.subjects_path(registries_dir)
    rows = [r for r in (subjects_table.row_from_subject_block(b) for b in blocks) if r]
    stats = subjects_table.upsert_subjects(registries_dir, rows, log=log,
                                           _hold_lock=False)
    still = set()
    for r in _rows(os.path.join(registries_dir, "registry_raw.csv")):
        still.update(x.strip() for x in (r.get("subject_ids") or "").split(";"))
    table = subjects_table.read_subjects(path)
    dropped = []
    for old in sorted({i["old_id"] for i in work}):
        if old in still:
            log(f"{old} is still referenced by an acquisition - left in place", "WARN")
        elif old in table:
            del table[old]
            dropped.append(old)
    if dropped:
        subjects_table.write_subjects(path, table)
    return stats, dropped, len(table)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--nas-root", default=os.environ.get("GJESUS3_ROOT", "/mnt/gjesus3"))
    p.add_argument("--backup-dir", default=os.path.join(
        os.path.expanduser("~"), "temp",
        f"gjesus3_proj0056_fix_{datetime.now():%Y%m%d}"))
    p.add_argument("--apply", action="store_true",
                   help="actually write (default: dry run, touches nothing)")
    args = p.parse_args(argv)

    registries = os.path.join(args.nas_root, "registries")
    if not os.path.isdir(registries):
        log(f"no registries/ under {args.nas_root!r}", "ERROR")
        return 2

    work, unresolvable = build_worklist(args.nas_root)
    for acq, code, name in unresolvable:
        log(f"{acq}: series={code!r} project={name!r} - cannot derive an animal, "
            f"SKIPPED, repair by hand", "ERROR")
    log(f"worklist: {len(work)} acquisition(s), "
        f"{len({i['old_id'] for i in work})} wrong id(s) -> "
        f"{len({i['new_id'] for i in work})} correct id(s)")
    if not work:
        log("nothing to do.")
        return 1 if unresolvable else 0
    for i in work:
        log(f"  {i['acq_id']}: {i['old_id']} -> {i['new_id']}")

    # Pre-flight: every sidecar cross-checked and every DB lookup made BEFORE
    # anything is written, so a missing animal aborts with nothing half-done.
    blocks = [fix_sidecar(i, apply=False) for i in work]
    resumed = sum(1 for i in work if i.get("already"))
    log(f"{len(blocks)} sidecar(s) cross-checked + resolved against the facility DB"
        + (f"; {resumed} already repaired by an earlier interrupted run" if resumed else ""))
    for b in {x["facility_animal_id"]: x for x in blocks}.values():
        log(f"  {b['facility_animal_id']}: dob={b['date_of_birth']} "
            f"sex={b['sex']} age={b['age_at_acquisition']} "
            f"procedures={len(b['procedures'])}")

    if not args.apply:
        log("DRY RUN - nothing written. Re-run with --apply.")
        return 0

    backup_registries(registries, args.backup_dir)

    blocks = [fix_sidecar(i, apply=True) for i in work]
    log(f"{len(blocks) - resumed} sidecar(s) rewritten + verified"
        + (f", {resumed} already correct and left alone" if resumed else ""))

    with locking.registry_lock(registries, log=log):
        changed = fix_registry_raw(
            os.path.join(registries, "registry_raw.csv"), work)
        log(f"registry_raw.csv: {changed} line(s) rewritten")
        stats, dropped, total = fix_subjects(registries, blocks, work)
        log(f"registry_subjects.csv: {stats['inserted']} inserted, "
            f"{stats['updated']} updated, {len(dropped)} stale row(s) dropped "
            f"({', '.join(dropped) or 'none'}), {total} rows total")

    if changed != len(work):
        log(f"registry_raw changed {changed} lines but the worklist had "
            f"{len(work)} - INVESTIGATE", "ERROR")
        return 1
    log("done. Verify with validate_registries.py (expect 0 errors).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
