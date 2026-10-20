#!/usr/bin/env python3
"""relink_subjects.py — move acquisitions to the right animal, or unlink them, from a worklist.

For acquisitions whose subject link is WRONG: the label named the wrong protocol
or the wrong animal number, so the subject record in production belongs to
another animal. The ACQ-IDs and the files never change; only the subject link
does (the recovery pattern: an in-place, verified correction of what ingest
recorded, never a re-ingest).

THE WORKLIST (CSV, UTF-8; one row per acquisition):
    acq_id      the acquisition to correct
    old_id      the subject id it carries now (must match the registry AND the sidecar)
    new_id      the canonical id of the right animal, or BLANK to unlink (no
                animal can be named from the evidence)
    new_db_id   optional: the facility DB animals.id the new id must resolve to
                on the acquisition day (a guard against a wrong worklist row)
    evidence    free text: why (kept in the worklist, the run log and the CHANGELOG)

PER ROW
    new_id set  the DATED lookup (animal_db) must find the animal that held
                new_id on the acquisition day; the sidecar's subject block is
                rebuilt from that record (enrichment._finalize_subject, so the
                field order and sentinels match 08_METADATA §4.4.2); the
                operator's weight is kept. A pending recovery row for the
                acquisition is flipped to recovered.
    new_id ""   the subject block becomes the `unknown` placeholder and the
                registry's subject_ids is blanked. The old label stays visible
                where the instrument wrote it (discovered.*, DICOM headers).

WRITES, in order (dry run by default; --apply to write):
    0. backups of every registry CSV and of each sidecar to be rewritten,
       byte-identical or abort;
    1. each `/raw/<acq>/metadata.json`: atomic, verified after write, its line
       terminator preserved (recover_subject_metadata._write_sidecar);
    2. under the registry lock: `registry_raw.csv` in BYTES (no BOM, CRLF kept),
       only the subject_ids field of the named rows; the pending list; and
       `registry_subjects.csv` (upsert of the new animals; a stub row
       (`pending-db` / `unknown`) that nothing references any more is dropped;
       a DB-filled row is never dropped).

Only single-animal rows are handled: a multi-animal `a;b` cell is refused.
Idempotent: a row already carrying new_id in both places is skipped.

Usage:
    python tools/relink_subjects.py --nas-root J:\\gjesus3-data --worklist <csv>
    python tools/relink_subjects.py --nas-root J:\\gjesus3-data --worklist <csv> --apply --backup-dir <dir>
"""

import argparse
import csv
import filecmp
import glob
import io
import os
import shutil
import sys
from datetime import datetime, timezone

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import animal_db  # noqa: E402
from ingest import enrichment, locking, pending, registry, subjects_table  # noqa: E402
from recover_subject_metadata import (  # noqa: E402  (reuse, don't re-implement)
    _read_sidecar, _verify_after_write, _write_sidecar, find_acquisition_datetime)

WORKLIST_FIELDS = ["acq_id", "old_id", "new_id", "new_db_id", "evidence"]
_STUB_SOURCES = ("pending-db", "unknown", "")


def log(msg, level="INFO"):
    print(f"[{datetime.now():%H:%M:%S}] {level}: {msg}", file=sys.stderr)


def read_worklist(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    missing = [c for c in ("acq_id", "old_id", "new_id") if rows and c not in rows[0]]
    if missing:
        raise RuntimeError(f"worklist {path} lacks column(s) {missing}")
    seen = set()
    for r in rows:
        if r["acq_id"] in seen:
            raise RuntimeError(f"worklist names {r['acq_id']} twice")
        seen.add(r["acq_id"])
    return rows


def backup(paths, dest):
    """Copy each file into `dest` (keeping a relative tail), byte-identical or abort."""
    os.makedirs(dest, exist_ok=True)
    for src, rel in paths:
        dst = os.path.join(dest, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        if not filecmp.cmp(src, dst, shallow=False):
            raise RuntimeError(f"backup of {src} is NOT byte-identical - aborting")
    log(f"backed up {len(paths)} file(s) to {dest} (verified)")


def _subject_blocks(sidecar):
    out = []
    if isinstance(sidecar.get("subject"), dict):
        out.append(("subject", sidecar["subject"]))
    for i, b in enumerate(sidecar.get("subjects") or []):
        if isinstance(b, dict):
            out.append((f"subjects[{i}]", b))
    return out


def plan(nas_root, worklist, lookup_fn=animal_db.lookup):
    """Cross-check every worklist row and build the corrected blocks. Writes nothing.

    Returns a list of items {acq_id, old_id, new_id, sidecar, block, labels,
    already, db_id, evidence}. Raises RuntimeError on the first row that does not
    match what production holds, so a bad worklist aborts with nothing written.
    """
    registries_dir = os.path.join(nas_root, "registries")
    reg = {r["acq_id"]: r for r in registry.read_registry(
        os.path.join(registries_dir, "registry_raw.csv"))}
    table = subjects_table.read_subjects(subjects_table.subjects_path(registries_dir))
    items = []
    for w in worklist:
        acq, old, new = w["acq_id"].strip(), w["old_id"].strip(), (w.get("new_id") or "").strip()
        r = reg.get(acq)
        if r is None:
            raise RuntimeError(f"{acq}: not in registry_raw.csv")
        cell = (r.get("subject_ids") or "").strip()
        if ";" in cell:
            raise RuntimeError(f"{acq}: multi-animal subject_ids {cell!r} - not handled here")
        side = os.path.join(nas_root, *r["canonical_path"].strip("/").split("/"), "metadata.json")
        if not os.path.isfile(side):
            raise RuntimeError(f"{acq}: no sidecar at {side}")
        md = _read_sidecar(side)
        blocks = _subject_blocks(md)
        ids = {b.get("facility_animal_id") or "" for _l, b in blocks}
        already = cell == new and ids == {new}
        if not already and (cell != old or ids != {old}):
            raise RuntimeError(f"{acq}: registry {cell!r} / sidecar {sorted(ids)} do not both "
                               f"carry old_id {old!r} - refusing to guess")
        item = {"acq_id": acq, "old_id": old, "new_id": new, "sidecar": side,
                "labels": [l for l, _b in blocks], "already": already, "db_id": None,
                "evidence": w.get("evidence", ""), "sample_type": r.get("sample_type", "")}
        if already:
            items.append(item)
            continue
        current = blocks[0][1]
        if new:
            alias, code = animal_db.parse_subject_id(new)
            day = animal_db.acq_id_day(acq)
            in_vivo = (r.get("sample_type") or "").strip().lower() != "tissue"
            res = lookup_fn(alias, code, on_date=day, in_vivo=in_vivo)
            if res.status != "found":
                raise RuntimeError(f"{acq}: {new} on {day}: {res.status} ({res.reason}): "
                                   f"{res.detail} - refusing to invent a subject")
            want = (w.get("new_db_id") or "").strip()
            got = res.subject.get("facility_db_id")
            if want and str(got) != want:
                raise RuntimeError(f"{acq}: {new} on {day} is DB animal {got}, the worklist "
                                   f"expects {want}")
            block = enrichment._finalize_subject(
                dict(res.subject), find_acquisition_datetime(md) or str(day), "animal-facility-db")
            if block["facility_animal_id"] != new:
                raise RuntimeError(f"{acq}: DB composed {block['facility_animal_id']!r}, "
                                   f"expected {new!r}")
            # The DB never supplies weight; keep whatever the operator/instrument gave.
            if current.get("weight_at_acquisition_g") is not None:
                block["weight_at_acquisition_g"] = current["weight_at_acquisition_g"]
            # The subjects table would refuse a second animal under this id; find
            # out now, before anything is written, not halfway through.
            existing = table.get(new)
            if existing and subjects_table.db_id_conflict(existing, {"facility_db_id": got}):
                raise RuntimeError(f"{acq}: registry_subjects.csv already names {new} as DB animal "
                                   f"{existing.get('facility_db_id')}, not {got}")
            item["db_id"] = got
            item["warnings"] = list(res.warnings)
        else:
            block = enrichment._subject_placeholder("unknown")
        item["block"] = block
        items.append(item)
    return items


def write_sidecar(item):
    """Replace every subject block of the sidecar with the corrected one; verify."""
    md = _read_sidecar(item["sidecar"])
    for label in item["labels"]:
        if label == "subject":
            md["subject"] = dict(item["block"])
        else:
            md["subjects"][int(label[len("subjects["):-1])] = dict(item["block"])
    _write_sidecar(item["sidecar"], md)
    ok, detail = _verify_after_write(
        item["sidecar"], {label: {"facility_animal_id": item["new_id"],
                                  "facility_db_id": item["block"]["facility_db_id"]}
                          for label in item["labels"]})
    if not ok:
        raise RuntimeError(f"{item['acq_id']}: verify-after-write failed: {detail}")


def _field_span(text, col):
    """(start, end) of the col-th field of one CSV line, honouring quotes."""
    start, n, quoted = 0, 0, False
    for i, ch in enumerate(text):
        if ch == '"':
            quoted = not quoted
        elif ch == "," and not quoted:
            if n == col:
                return start, i
            n, start = n + 1, i + 1
    if n == col:
        end = len(text.rstrip("\r\n"))
        return start, end
    raise RuntimeError(f"line has no field {col}")


def rewrite_registry_raw(path, items):
    """Change ONLY the subject_ids field of the named rows, in BYTES.

    The live file has no BOM and CRLF endings; a csv round-trip would re-quote
    and re-terminate 40k rows. Each target line is parsed to find the field,
    whose exact span is replaced (an id never needs quoting, so a quoted cell
    is refused), and the line is parsed again to prove that nothing else
    moved. Returns the number of lines changed."""
    by_acq = {i["acq_id"]: i for i in items if not i["already"]}
    with open(path, "rb") as f:
        lines = f.readlines()
    header = next(csv.reader(io.StringIO(lines[0].decode("utf-8-sig"))))
    col = header.index("subject_ids")
    changed = 0
    for n, line in enumerate(lines[1:], start=1):
        acq = line.split(b",", 1)[0].decode("utf-8", "replace")
        item = by_acq.get(acq)
        if item is None:
            continue
        text = line.decode("utf-8")
        before = next(csv.reader(io.StringIO(text)))
        if before[col] != item["old_id"]:
            raise RuntimeError(f"{acq}: subject_ids is {before[col]!r}, expected {item['old_id']!r}")
        s, e = _field_span(text, col)
        if text[s:e] != item["old_id"]:
            raise RuntimeError(f"{acq}: subject_ids cell is {text[s:e]!r} in the file - refusing")
        text = text[:s] + item["new_id"] + text[e:]
        after = next(csv.reader(io.StringIO(text)))
        expect = list(before)
        expect[col] = item["new_id"]
        if after != expect:
            raise RuntimeError(f"{acq}: the byte edit changed more than subject_ids - aborting")
        lines[n] = text.encode("utf-8")
        changed += 1
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "wb") as f:
        f.writelines(lines)
    os.replace(tmp, path)
    return changed


def flip_pending(registries_dir, items, now):
    """A pending recovery row for an acquisition now filled from the DB -> recovered."""
    path = pending.pending_path(registries_dir)
    rows = pending.read_pending(path)
    filled = {i["acq_id"] for i in items if not i["already"] and i["new_id"]}
    flipped = 0
    for r in rows:
        if r.get("acq_id") in filled and (r.get("status") or "").strip() == "pending":
            r["status"] = "recovered"
            r["recovered_at"] = now
            flipped += 1
    if flipped:
        pending._assert_header(path)
        pending._write_all(path, rows)
    return flipped


def update_subjects(registries_dir, items, now):
    """Upsert the new animals, then drop stub rows nothing references any more."""
    rows = [r for r in (subjects_table.row_from_subject_block(i["block"])
                        for i in items if not i["already"] and i["new_id"]) if r]
    stats = subjects_table.upsert_subjects(registries_dir, rows, now=now, log=log,
                                           _hold_lock=False)
    if stats["conflict"]:
        raise RuntimeError(f"registry_subjects.csv refused {stats['conflicts']} - investigate")
    still = set()
    for r in registry.read_registry(os.path.join(registries_dir, "registry_raw.csv")):
        still.update(x.strip() for x in (r.get("subject_ids") or "").split(";"))
    path = subjects_table.subjects_path(registries_dir)
    table = subjects_table.read_subjects(path)
    dropped, kept = [], []
    for old in sorted({i["old_id"] for i in items}):
        if old in still or old not in table:
            continue
        if (table[old].get("source") or "") in _STUB_SOURCES:
            del table[old]
            dropped.append(old)
        else:
            kept.append(old)
    if dropped:
        subjects_table.write_subjects(path, table)
    return stats, dropped, kept


def verify(nas_root, items):
    """Re-read what was written and confirm every row; returns a list of problems."""
    registries_dir = os.path.join(nas_root, "registries")
    reg = {r["acq_id"]: r for r in registry.read_registry(
        os.path.join(registries_dir, "registry_raw.csv"))}
    table = subjects_table.read_subjects(subjects_table.subjects_path(registries_dir))
    problems = []
    for i in items:
        if (reg[i["acq_id"]].get("subject_ids") or "") != i["new_id"]:
            problems.append(f"{i['acq_id']}: registry subject_ids is not {i['new_id']!r}")
        md = _read_sidecar(i["sidecar"])
        if {b.get("facility_animal_id") or "" for _l, b in _subject_blocks(md)} != {i["new_id"]}:
            problems.append(f"{i['acq_id']}: sidecar does not carry {i['new_id']!r}")
        if i["new_id"]:
            row = table.get(i["new_id"])
            if not row:
                problems.append(f"{i['acq_id']}: {i['new_id']} missing from registry_subjects.csv")
            elif i["db_id"] is not None and row.get("facility_db_id") not in ("", str(i["db_id"])):
                problems.append(f"{i['new_id']}: subjects row names DB animal "
                                f"{row.get('facility_db_id')}, expected {i['db_id']}")
    return problems


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--nas-root", default=os.environ.get("GJESUS3_ROOT", "/mnt/gjesus3"))
    p.add_argument("--worklist", required=True)
    p.add_argument("--backup-dir", default=os.path.join(
        os.path.expanduser("~"), "temp", f"gjesus3_relink_subjects_{datetime.now():%Y%m%d_%H%M%S}"))
    p.add_argument("--apply", action="store_true",
                   help="actually write (default: dry run, touches nothing)")
    args = p.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    registries_dir = os.path.join(args.nas_root, "registries")
    if not os.path.isdir(registries_dir):
        log(f"no registries/ under {args.nas_root!r}", "ERROR")
        return 2

    worklist = read_worklist(args.worklist)
    items = plan(args.nas_root, worklist)
    todo = [i for i in items if not i["already"]]
    log(f"worklist: {len(items)} acquisition(s); {len(items) - len(todo)} already done; "
        f"{len(todo)} to change ({sum(1 for i in todo if not i['new_id'])} unlink)")
    for i in todo:
        b = i["block"]
        log(f"  {i['acq_id']}: {i['old_id']} -> {i['new_id'] or '(unlinked)'}"
            + (f"  DB id {i['db_id']}, dob {b['date_of_birth']}, sex {b['sex']}, "
               f"age {b['age_at_acquisition']}" if i["new_id"] else "")
            + (f"  warnings {i['warnings']}" if i.get("warnings") else ""))
    if not todo:
        log("nothing to do.")
        return 0
    if not args.apply:
        log("DRY RUN - nothing written. Re-run with --apply.")
        return 0

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    files = [(f, os.path.join("registries", os.path.basename(f)))
             for f in sorted(glob.glob(os.path.join(registries_dir, "*.csv")))]
    files += [(i["sidecar"], os.path.join("sidecars", i["acq_id"], "metadata.json")) for i in todo]
    backup(files, args.backup_dir)

    for i in todo:
        write_sidecar(i)
    log(f"{len(todo)} sidecar(s) rewritten + verified")
    with locking.registry_lock(registries_dir, log=log):
        changed = rewrite_registry_raw(os.path.join(registries_dir, "registry_raw.csv"), items)
        log(f"registry_raw.csv: {changed} line(s) rewritten")
        flipped = flip_pending(registries_dir, items, now)
        log(f"pending_subject_metadata.csv: {flipped} row(s) flipped to recovered")
        stats, dropped, kept = update_subjects(registries_dir, items, now)
        log(f"registry_subjects.csv: {stats['inserted']} inserted, {stats['updated']} updated; "
            f"stub rows dropped: {', '.join(dropped) or 'none'}; unreferenced DB rows kept: "
            f"{', '.join(kept) or 'none'}")
    problems = verify(args.nas_root, items)
    for m in problems:
        log(m, "ERROR")
    if problems or changed != len(todo):
        log(f"verification FAILED ({len(problems)} problem(s); {changed}/{len(todo)} lines) "
            f"- backups in {args.backup_dir}", "ERROR")
        return 1
    log(f"done and verified. Backups in {args.backup_dir}. "
        f"Run validate_registries.py next (expect 0 errors).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
