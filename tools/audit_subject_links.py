#!/usr/bin/env python3
"""audit_subject_links.py — read-only audit of every subject link against the DATED lookup.

Every (acquisition, subject) link in `registry_raw.subject_ids` whose id has the
canonical `<code>-AE-biomaGUNE-<NNNN>` form is put through animal_db's dated,
transfer-aware lookup (the animal that held the code on the acquisition day)
and compared with what the old date-blind lookup answered (the code's CURRENT
holder). The facility DB is read once (SELECT only); the NAS is only read.

Each link gets one category:

  unchanged               the record came from the DB and the dated lookup picks
                          the same animal; only `facility_db_id` would be added.
  wrong:refused           the record came from the DB, but no animal held the code
                          that day (or the date precedes the animal's birth): the
                          record in production belongs to an animal that cannot
                          be the one acquired. A label error; no join can fix it.
  wrong:other-animal      the record came from the DB, but names another animal
                          than the one that held the code that day (the subjects
                          table's facility_db_id when it has one, else the code's
                          current holder, which the old lookup returned).
  recoverable:dated       pending; only the dated lookup finds the right animal,
                          through a transfer, because the DB also lists this
                          (protocol, code) on a LATER record (the old lookup
                          would have written that one).
  recoverable:transfer    pending; found through a transfer; no later record
                          carries the code.
  recoverable             pending; found directly (the DB was just not reached).
  still-pending           pending, and the dated lookup cannot answer either.
  not-db                  the subject was not from the DB (operator-entered, ...).

Soft signals on a found link go in `warnings`: `after-exit` (an in-vivo scan
dated after the animal's DB exit) and `tissue-before-exit` (a tissue specimen
dated while the animal was alive). They change nothing; they point at labels
worth a look.

Writes two files to --out (a local folder, never the NAS):
  subject_link_audit.csv   one row per link, with what would change;
  subject_link_audit.txt   the counts.

Usage:
    python tools/audit_subject_links.py --nas-root J:\\gjesus3-data --out <local folder>
"""

import argparse
import csv
import os
import sys
from collections import Counter

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import animal_db  # noqa: E402
from ingest import pending, registry, subjects_table  # noqa: E402

AUDIT_FIELDS = [
    "acq_id", "instrument", "sample_type", "acq_day", "subject_id", "table_source",
    "pending_status", "category", "warnings", "old_db_id", "new_db_id", "new_kind",
    "current_facility_id", "table_dob", "new_dob", "table_sex", "new_sex",
    "would_change", "detail", "project_id", "original_name",
]


def _date_blind_holder(index, alias, code):
    """What the pre-2026-10-20 lookup answered: the code's CURRENT holder
    (`id_project = P AND animal_code = c LIMIT 1`), ignoring the date."""
    proj = index.project(alias)
    if not proj:
        return None
    current = [h for h in animal_db.build_holders(index.holder_rows(proj["id"], code),
                                                  proj["id"], code)
               if h["kind"] == "current"]
    return min(current, key=lambda h: h["row"]["id"])["row"] if current else None


def classify(link, index, table_row, pending_row):
    """One audit row for one (acquisition, subject) link. Pure over the index."""
    fid, acq = link["subject_id"], link["acq_id"]
    alias, code = animal_db.parse_subject_id(fid)
    in_vivo = link["sample_type"] != "tissue"
    day = animal_db.acq_id_day(acq)
    res = animal_db.lookup(alias, code, on_date=day, in_vivo=in_vivo, index=index)
    blind = _date_blind_holder(index, alias, code)
    source = (table_row or {}).get("source", "")
    pstatus = (pending_row or {}).get("status", "")
    is_pending = source == "pending-db" or pstatus == "pending"
    new = res.subject or {}
    # The animal the record names: its stored DB id when the subjects table has
    # one (after 2026-10-20), else what the date-blind lookup would have given.
    stored = str((table_row or {}).get("facility_db_id") or "").strip()
    old_id = int(stored) if stored.isdigit() else (blind["id"] if blind else "")
    new_id = new.get("facility_db_id", "")

    if source in ("animal-facility-db",) and not is_pending:
        if res.status != "found":
            cat = "wrong:refused"
            change = "withdraw the DB record (it cannot be this animal); find the right label"
        elif new_id != old_id:
            cat = "wrong:other-animal"
            change = f"refill from DB id {new_id} (was {old_id})"
        else:
            cat = "unchanged"
            change = f"add facility_db_id {new_id}"
    elif is_pending:
        if res.status != "found":
            cat = "still-pending"
            change = "none"
        elif res.holder["kind"] == "moved-out":
            cat = "recoverable:dated" if blind else "recoverable:transfer"
            change = (f"fill from DB id {new_id} (now {res.holder['current_facility_id']})"
                      + (f"; the old lookup would have written DB id {old_id}" if blind else ""))
        else:
            cat = "recoverable"
            change = f"fill from DB id {new_id}"
    else:
        cat = "not-db"
        change = "none"

    return {
        "acq_id": acq, "instrument": link["instrument"], "sample_type": link["sample_type"],
        "acq_day": day.isoformat() if day else "", "subject_id": fid,
        "table_source": source, "pending_status": pstatus, "category": cat,
        "warnings": ";".join(res.warnings), "old_db_id": old_id, "new_db_id": new_id,
        "new_kind": (res.holder or {}).get("kind", ""),
        "current_facility_id": (res.holder or {}).get("current_facility_id", ""),
        "table_dob": (table_row or {}).get("date_of_birth", ""),
        "new_dob": new.get("date_of_birth") or "",
        "table_sex": (table_row or {}).get("sex", ""), "new_sex": new.get("sex", ""),
        "would_change": change, "detail": res.detail,
        "project_id": link["project_id"], "original_name": link["original_name"],
    }


def links_of(acqs):
    """(acquisition, canonical subject id) pairs from registry_raw rows."""
    for r in acqs:
        for fid in (x.strip() for x in (r.get("subject_ids") or "").split(";")):
            if not fid:
                continue
            try:
                animal_db.parse_subject_id(fid)
            except ValueError:
                continue
            yield {"acq_id": r.get("acq_id", ""), "subject_id": fid,
                   "instrument": r.get("instrument", ""),
                   "sample_type": (r.get("sample_type") or "").strip().lower(),
                   "project_id": r.get("project_id", ""),
                   "original_name": r.get("original_name", "")}


def audit(registries_dir, index):
    """Every link, classified. Returns the list of audit rows."""
    acqs = registry.read_registry(os.path.join(registries_dir, "registry_raw.csv"))
    table = subjects_table.read_subjects(subjects_table.subjects_path(registries_dir))
    pend = {r["acq_id"]: r for r in pending.read_pending(pending.pending_path(registries_dir))}
    return [classify(link, index, table.get(link["subject_id"]), pend.get(link["acq_id"]))
            for link in links_of(acqs)]


def summarize(rows):
    lines = [f"links audited: {len(rows)}"]
    cats = Counter(r["category"] for r in rows)
    lines.append("by category:")
    lines += [f"   {c:<24} {n}" for c, n in cats.most_common()]
    lines.append("by category x warning:")
    for (c, w), n in sorted(Counter((r["category"], r["warnings"] or "-") for r in rows).items()):
        lines.append(f"   {c:<24} {w:<20} {n}")
    lines.append("non-unchanged by category x protocol x instrument:")
    for (c, p, i), n in sorted(Counter(
            (r["category"], r["subject_id"].rsplit("-", 1)[-1], r["instrument"])
            for r in rows if r["category"] != "unchanged").items()):
        lines.append(f"   {c:<24} {p:<8} {i:<6} {n}")
    lines.append("distinct subject ids by category:")
    for c in sorted(cats):
        lines.append(f"   {c:<24} {len({r['subject_id'] for r in rows if r['category'] == c})}")
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--nas-root", default=os.environ.get("GJESUS3_ROOT", "/mnt/gjesus3"))
    p.add_argument("--out", required=True, help="local folder for the two report files")
    args = p.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    registries_dir = os.path.join(args.nas_root, "registries")
    if not os.path.isdir(registries_dir):
        print(f"no registries/ under {args.nas_root!r}", file=sys.stderr)
        return 2
    out = os.path.abspath(args.out)
    if os.path.abspath(args.nas_root).lower() in out.lower():
        print("refusing to write the report under the NAS root", file=sys.stderr)
        return 2
    os.makedirs(out, exist_ok=True)

    conn = animal_db.get_connection()
    try:
        index = animal_db.HolderIndex.from_connection(conn)
    finally:
        conn.close()
    rows = audit(registries_dir, index)

    with open(os.path.join(out, "subject_link_audit.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=AUDIT_FIELDS)
        w.writeheader()
        w.writerows(rows)
    text = summarize(rows)
    with open(os.path.join(out, "subject_link_audit.txt"), "w", encoding="utf-8", newline="\n") as f:
        f.write(text + "\n")
    print(text)
    print(f"\nwritten: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
